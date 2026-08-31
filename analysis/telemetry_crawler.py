"""
Intra-day micro-drift telemetry crawler.

Pulls the FULL 156-qubit calibration snapshot (readout + T1/T2 + sx) from one or
more IBM Quantum backends via the classic `backend.properties()` REST call.
This costs ZERO QPU seconds and ZERO money -- it is a pure classical properties
request (~1.2 s).

Purpose (paper task 1): show that staleness is NOT a day-scale problem but a
QUEUE-WAIT-scale problem. IBM runs one big calibration per day (~19-20 h local);
within 4-8 h -- well inside a real user's job-queue wait -- the top-k Jaccard vs
the post-calibration baseline should already drop below 0.5. We also log |dC| on
every adjacent snapshot pair, which feeds the Survival Analysis (task 3).

Usage:
  python telemetry_crawler.py --once --backend ibm_marrakesh
      # single immediate pull (establishes the t0 baseline per calibration epoch)
  python telemetry_crawler.py --backend ibm_marrakesh --interval 10800 --days 7
      # loop every 3 h for 7 days
  python telemetry_crawler.py --backends ibm_marrakesh,ibm_kingston --interval 7200
      # multiple devices, every 2 h

Output:
  data/calib_snapshots/<backend>/<ISO-utc>.json   full snapshot (calib_ format)
  data/calib_snapshots/telemetry_log.jsonl        one summary row per pull
"""
import argparse
import datetime
import json
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from tenacity import retry, stop_after_attempt, wait_exponential

ROOT = Path(r"C:\Users\SCSM11\Desktop\unimind-v2")
SNAP_DIR = ROOT / "data" / "calib_snapshots"
SNAP_DIR.mkdir(parents=True, exist_ok=True)
LOG = SNAP_DIR / "telemetry_log.jsonl"

# reuse the validated fetch_table + fetch machinery (works on qiskit 2.5.1)
sys.path.insert(0, str(ROOT / "analysis"))
import hw_router  # noqa: E402

# round-robin single instance so concurrent threads share it cheaply
_service_lock = threading.Lock()
_service = None


def get_service():
    global _service
    with _service_lock:
        if _service is None:
            import warnings
            warnings.filterwarnings("ignore")
            from qiskit_ibm_runtime import QiskitRuntimeService
            _service = QiskitRuntimeService()
        return _service


def utcnow_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def jacc(a, b, k=10):
    sa = set(a[:k]); sb = set(b[:k])
    return len(sa & sb) / max(len(sa | sb), 1)


def summarize_snapshot(snap):
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


@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=60),
       reraise=True)
def _fetch_table(service, backend_name):
    """Single backend.properties() pull with exponential-backoff retry on
    RateLimit/Timeout/transient errors so a flaky free-tier API never drops a
    time point (survival analysis needs a gapless time series)."""
    backend = service.backend(backend_name)
    return hw_router.fetch_table(backend)


def pull(backend_name, verbose=True):
    """Fetch one full snapshot + summary. Dual-timestamped: files and logs carry
    BOTH fetch_time_utc (local request time) and the device calibration time
    (last_update_date). Returns (snap, summary, path) or None on unrecoverable error."""
    service = get_service()
    try:
        snap = _fetch_table(service, backend_name)
    except Exception as e:
        print(f"[{utcnow_iso()}] {backend_name} UNRECOVERABLE after retries: {e}")
        return None
    fetch_utc = utcnow_iso()
    snap["fetch_time_utc"] = fetch_utc
    iso = fetch_utc.replace(":", "").replace("+00:00", "Z")
    path = SNAP_DIR / backend_name / f"{iso}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snap, indent=2, ensure_ascii=False))
    return snap, summarize_snapshot(snap), path, iso


def est_hours_since_calib(snap):
    """Hours between the snapshot's own last_update_date (calibration time) and now."""
    try:
        lu = datetime.datetime.fromisoformat(snap["last_update_date"].replace("Z", "+00:00"))
        if lu.tzinfo is None:
            lu = lu.replace(tzinfo=datetime.timezone.utc)
        now = datetime.datetime.now(lu.tzinfo)
        return max(0.0, (now - lu).total_seconds() / 3600.0)
    except Exception:
        return float("nan")


def _api_staleness_sec(fetch_utc, last_update):
    """Seconds between the local fetch time and the device calibration time
    (a cloud staleness-at-fetch measure; == hours_since_calib in seconds)."""
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backends", default="ibm_marrakesh",
                    help="comma-separated backend names")
    ap.add_argument("--backend", default=None, help="single backend (shorthand)")
    ap.add_argument("--interval", type=float, default=10800,
                    help="seconds between pulls (2-4 h recommended: 7200-14400)")
    ap.add_argument("--days", type=float, default=7)
    ap.add_argument("--once", action="store_true", help="pull once and exit")
    args = ap.parse_args()

    backends = [args.backend] if args.backend else args.backends.split(",")
    backends = [b.strip() for b in backends if b.strip()]

    # per-backend running state: baseline of the current calibration epoch
    epoch = {b: {"baseline_sorted": None, "baseline_last_update": None} for b in backends}

    print(f"Telemetry crawler: {backends}  interval={args.interval}s  (0 QPU)")
    deadline = time.time() + args.days * 86400
    while True:
        # concurrent pull across backends; a failed one returns None and is skipped
        results = {}
        with ThreadPoolExecutor(max_workers=len(backends)) as ex:
            futures = {ex.submit(pull, b): b for b in backends}
            for fut in as_completed(futures):
                bname = futures[fut]
                try:
                    results[bname] = fut.result()
                except Exception as e:
                    print(f"[{utcnow_iso()}] {bname} worker error: {e}")
                    results[bname] = None

        for bname in backends:
            res = results.get(bname)
            if res is None:
                continue
            snap, summ, path, iso = res
            st = epoch[bname]
            hrs = est_hours_since_calib(snap)
            rows = sorted(snap["qubits"], key=lambda r: r["readout_total"])
            order = [r["q"] for r in rows]

            # new calibration epoch?
            if st["baseline_last_update"] != snap["last_update_date"]:
                st["baseline_sorted"] = order
                st["baseline_last_update"] = snap["last_update_date"]
                j1 = j3 = j10 = 1.0
            else:
                base = st["baseline_sorted"]
                j1 = jacc(order, base, 1)
                j3 = jacc(order, base, 3)
                j10 = jacc(order, base, 10)

            row = {
                "fetched_at": snap.get("fetched_at"),
                "fetch_time_utc": summ["fetch_time_utc"],
                "backend": bname,
                "last_update": snap["last_update_date"],
                "api_staleness_s": _api_staleness_sec(summ["fetch_time_utc"], snap["last_update_date"]),
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
            with LOG.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
            print(f"[{row['fetched_at']}] {bname}: hrs={row['hours_since_calib']:>5.2f} "
                  f"J10={row['jacc_top10']:.2f} best_rt={row['best_rt']:.5f} "
                  f"med_rt={row['median_rt']:.5f} -> {path.name}")

        if args.once:
            break
        if time.time() >= deadline:
            print("interval complete")
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
