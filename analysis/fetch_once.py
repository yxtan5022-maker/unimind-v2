"""
fetch_once.py -- single-run telemetry fetcher (replaces telemetry_crawler loop mode).

Design:
  - Single invocation: fetch calibration snapshot for each device, append to JSONL.
  - Deduplication: skip if last_update_date already logged for that backend.
  - Retry: exponential backoff, 3 attempts, try/except wrapped.
  - Output: one summary line per device to stdout.
  - JSON handling: utf-8-sig for BOM, .strip() on all keys.

Usage:
  python fetch_once.py                          # default: ibm_marrakesh,ibm_fez,ibm_kingston
  python fetch_once.py --backends ibm_fez       # single device
  python fetch_once.py --dry-run                # fetch + print, do not write JSONL
"""
from __future__ import annotations

import argparse
import datetime
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\Users\SCSM11\Desktop\unimind-v2")
SNAP_DIR = ROOT / "data" / "calib_snapshots"
SNAP_DIR.mkdir(parents=True, exist_ok=True)
LOG = SNAP_DIR / "telemetry_log.jsonl"

sys.path.insert(0, str(ROOT / "analysis"))
import hw_router  # noqa: E402


# ── helpers ──────────────────────────────────────────────────────────────

def _get_service():
    import warnings
    warnings.filterwarnings("ignore")
    import logging
    logging.disable(logging.CRITICAL)
    from qiskit_ibm_runtime import QiskitRuntimeService
    return QiskitRuntimeService(
        channel="ibm_quantum_platform", instance="unimind 3.0")


def utcnow_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def jacc(a: list, b: list, k: int = 10) -> float:
    sa, sb = set(a[:k]), set(b[:k])
    return len(sa & sb) / max(len(sa | sb), 1)


def _api_staleness_sec(fetch_utc: str, last_update: str) -> float | None:
    try:
        fu = datetime.datetime.fromisoformat(fetch_utc)
        if fu.tzinfo is None:
            fu = fu.replace(tzinfo=datetime.timezone.utc)
        lu = datetime.datetime.fromisoformat(last_update.replace("Z", "+00:00"))
        if lu.tzinfo is None:
            lu = lu.replace(tzinfo=datetime.timezone.utc)
        return round((fu - lu).total_seconds(), 1)
    except Exception:
        return None


def est_hours_since_calib(snap: dict) -> float:
    try:
        lu = datetime.datetime.fromisoformat(snap["last_update_date"].replace("Z", "+00:00"))
        if lu.tzinfo is None:
            lu = lu.replace(tzinfo=datetime.timezone.utc)
        now = datetime.datetime.now(lu.tzinfo)
        return max(0.0, (now - lu).total_seconds() / 3600.0)
    except Exception:
        return float("nan")


def summarize_snapshot(snap: dict) -> dict:
    rows = snap["qubits"]
    rt = sorted(r["readout_total"] for r in rows)
    n = len(rt)
    return {
        "n": n,
        "median_rt": rt[n // 2],
        "min_rt": rt[0],
        "max_rt": rt[-1],
        "mean_rt": sum(rt) / n if n else 0.0,
        "best_q": min(rows, key=lambda r: r["readout_total"])["q"],
        "best_rt": rt[0],
        "top10": [q["q"] for q in sorted(rows, key=lambda r: r["readout_total"])[:10]],
        "last_update": snap["last_update_date"],
        "fetch_time_utc": snap.get("fetch_time_utc"),
    }


def _load_existing_keys() -> set[tuple[str, str]]:
    """Return set of (backend, last_update_date) already in JSONL."""
    keys = set()
    if LOG.exists():
        with LOG.open("r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    keys.add((row.get("backend", ""), row.get("last_update", "")))
                except json.JSONDecodeError:
                    continue
    return keys


def _strip_keys(obj):
    """Recursively .strip() all string keys in dicts."""
    if isinstance(obj, dict):
        return {k.strip() if isinstance(k, str) else k: _strip_keys(v)
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [_strip_keys(x) for x in obj]
    return obj


# ── core fetch with retry ───────────────────────────────────────────────

def fetch_backend(service, backend_name: str, max_retries: int = 3) -> dict | None:
    """Fetch one snapshot with exponential backoff retry. Returns snap dict or None."""
    last_err = None
    for attempt in range(max_retries):
        try:
            backend = service.backend(backend_name)
            snap = hw_router.fetch_table(backend)
            snap["fetch_time_utc"] = utcnow_iso()
            snap["backend"] = backend_name
            return _strip_keys(snap)
        except Exception as e:
            last_err = e
            wait = min(2 ** (attempt + 1), 60)
            if attempt < max_retries - 1:
                time.sleep(wait)
    print(f"[{utcnow_iso()}] {backend_name} FAIL after {max_retries} attempts: {last_err}")
    return None


# ── JSONL writer ─────────────────────────────────────────────────────────

def _read_baseline_from_jsonl(backend: str, existing_keys: set) -> dict | None:
    """Find the most recent row for this backend in JSONL (for Jaccard baseline)."""
    last_row = None
    if LOG.exists():
        with LOG.open("r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    if row.get("backend") == backend:
                        last_row = row
                except json.JSONDecodeError:
                    continue
    return last_row


def write_one(snap: dict, dry_run: bool = False) -> str | None:
    """Write snapshot file + JSONL row. Returns one-line summary or None."""
    backend = snap["backend"]
    fetch_utc = snap["fetch_time_utc"]
    iso = fetch_utc.replace(":", "").replace("+00:00", "Z")
    path = SNAP_DIR / backend / f"{iso}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snap, indent=2, ensure_ascii=False))

    summ = summarize_snapshot(snap)
    hrs = est_hours_since_calib(snap)
    rows = sorted(snap["qubits"], key=lambda r: r["readout_total"])
    order = [r["q"] for r in rows]

    prev = _read_baseline_from_jsonl(backend, set())
    if prev and prev.get("last_update") == snap["last_update_date"]:
        base_top10 = prev.get("top10", [])
        j10 = jacc(order, base_top10, 10)
        j1 = jacc(order, base_top10, 1)
        j3 = jacc(order, base_top10, 3)
    else:
        j1 = j3 = j10 = 1.0

    row = {
        "fetch_time_utc": fetch_utc,
        "backend": backend,
        "last_update": snap["last_update_date"],
        "api_staleness_s": _api_staleness_sec(fetch_utc, snap["last_update_date"]),
        "hours_since_calib": round(hrs, 2),
        "median_rt": round(summ["median_rt"], 5),
        "mean_rt": round(summ["mean_rt"], 5),
        "max_rt": round(summ["max_rt"], 5),
        "best_q": summ["best_q"],
        "best_rt": round(summ["best_rt"], 5),
        "top10": summ["top10"],
        "jacc_top1": round(j1, 3),
        "jacc_top3": round(j3, 3),
        "jacc_top10": round(j10, 3),
        "snapshot_file": str(path),
    }

    if not dry_run:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")

    summary = (f"{backend}: hrs={hrs:.2f} J10={j10:.2f} "
               f"best_rt={summ['best_rt']:.5f} med_rt={summ['median_rt']:.5f} -> {path.name}")
    return summary


# ── main ─────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Single-run telemetry fetcher")
    ap.add_argument("--backends", default="ibm_marrakesh,ibm_fez,ibm_kingston",
                    help="comma-separated backend names")
    ap.add_argument("--dry-run", action="store_true",
                    help="fetch and print but do not write JSONL")
    args = ap.parse_args()

    backends = [b.strip() for b in args.backends.split(",") if b.strip()]
    existing = _load_existing_keys()

    print(f"fetch_once: {backends} (existing rows: {len(existing)})")
    try:
        service = _get_service()
    except Exception as e:
        print(f"FAILED to init QiskitRuntimeService: {e}")
        sys.exit(1)

    for backend_name in backends:
        try:
            snap = fetch_backend(service, backend_name, max_retries=3)
        except Exception as e:
            print(f"[{utcnow_iso()}] {backend_name} UNEXPECTED: {e}")
            continue

        if snap is None:
            continue

        lu = snap.get("last_update_date", "")
        if (backend_name, lu) in existing:
            print(f"{backend_name}: SKIP (last_update={lu} already in JSONL)")
            continue

        summary = write_one(snap, dry_run=args.dry_run)
        if summary:
            print(summary)


if __name__ == "__main__":
    main()
