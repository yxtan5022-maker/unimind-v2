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
from pathlib import Path

ROOT = Path(r"C:\Users\SCSM11\Desktop\unimind-v2")
SNAP_DIR = ROOT / "data" / "calib_snapshots"
SNAP_DIR.mkdir(parents=True, exist_ok=True)
LOG = SNAP_DIR / "telemetry_log.jsonl"

# reuse the validated fetch_table + fetch machinery (works on qiskit 2.5.1)
sys.path.insert(0, str(ROOT / "analysis"))
import hw_router  # noqa: E402


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
        "best_q": min(rows, key=lambda r: r["readout_total"])["q"],
        "best_rt": rt[0],
        "last_update": snap["last_update_date"],
    }


def pull(service, backend_name, verbose=True):
    """Fetch one full snapshot and its summary."""
    backend = service.backend(backend_name)
    snap = hw_router.fetch_table(backend)
    iso = utcnow_iso().replace(":", "").replace("+00:00", "Z")
    path = SNAP_DIR / backend_name / f"{iso}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snap, indent=2, ensure_ascii=False))
    return snap, summarize_snapshot(snap), path


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

    import warnings
    warnings.filterwarnings("ignore")
    from qiskit_ibm_runtime import QiskitRuntimeService
    service = QiskitRuntimeService()

    # per-backend running state: baseline of the current calibration epoch
    epoch = {b: {"baseline_sorted": None, "baseline_last_update": None} for b in backends}

    print(f"Telemetry crawler: {backends}  interval={args.interval}s  (0 QPU)")
    deadline = time.time() + args.days * 86400
    first = True
    while True:
        try:
            for bname in backends:
                snap, summ, path = pull(service, bname)
                st = epoch[bname]
                hrs = est_hours_since_calib(snap)
                rows = sorted(snap["qubits"], key=lambda r: r["readout_total"])
                order = [r["q"] for r in rows]

                # new calibration epoch?
                if st["baseline_last_update"] != snap["last_update_date"]:
                    st["baseline_sorted"] = order
                    st["baseline_last_update"] = snap["last_update_date"]
                    j1 = j3 = j10 = 1.0
                    dC_best = 0.0
                    med_dC = 0.0
                else:
                    base = st["baseline_sorted"]
                    j1 = jacc(order, base, 1)
                    j3 = jacc(order, base, 3)
                    j10 = jacc(order, base, 10)
                    dC_best = 0.0        # computed in analysis from adjacent snapshots
                    med_dC = 0.0

                row = {
                    "fetched_at": snap.get("fetched_at"),
                    "backend": bname,
                    "last_update": snap["last_update_date"],
                    "hours_since_calib": round(hrs, 2),
                    "median_rt": round(summ["median_rt"], 5),
                    "best_q": summ["best_q"],
                    "best_rt": round(summ["best_rt"], 5),
                    "jacc_top1": round(j1, 3),
                    "jacc_top3": round(j3, 3),
                    "jacc_top10": round(j10, 3),
                    "snapshot_file": str(path),
                }
                with LOG.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(row) + "\n")
                print(f"[{row['fetched_at']}] {bname}: hrs={row['hours_since_calib']:>5.2f} "
                      f"J(top1/3/10)={row['jacc_top1']}/{row['jacc_top3']}/{row['jacc_top10']} "
                      f"best_rt={row['best_rt']:.5f} med_rt={row['median_rt']:.5f} -> {path.name}")
        except Exception as e:
            import traceback
            print(f"[{utcnow_iso()}] ERROR pulling: {e}")
            traceback.print_exc()

        if args.once:
            break
        if time.time() >= deadline:
            print("interval complete")
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
