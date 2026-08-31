"""
Survival Analysis of calibration validity (paper task 3).

Turns the if-else refresh trigger (if Jaccard<0.5 or dC>0.005: refresh) into a
principled, data-derived operating point.

Definitions (per calibration epoch -- a new daily calibration resets the clock):
  - time origin t=0  = the post-calibration baseline snapshot (Jaccard=1.0).
  - event (fail)     = at hour t the trigger would FIRE: top-10 Jaccard vs the
                       epoch baseline drops below tau_J=0.5, OR the stored best
                       qubit's dC exceeds tau_C=0.005.
  - survival time    = hours since calibration until the event; right-censored if
                       the snapshot survived to our last observation without firing.

Output:
  - Kaplan-Meier survival curve S(t) = P(snapshot still valid at hour t)
  - median survival time (first t with S(t)<=0.5)
  - the derived operating point: refresh every ~Q_median hours vs the current
    fixed if-else trigger.

Runs over whatever snapshot history exists in data/calib_snapshots/; recomputes
each time the crawler has collected more epochs, so 5-7 days of data yields the
full curve. Reads the same schema written by telemetry_crawler.py.
"""
import argparse
import datetime
import json
import sys
from pathlib import Path
import numpy as np

ROOT = Path(r"C:\Users\SCSM11\Desktop\unimind-v2")
SNAP_DIR = ROOT / "data" / "calib_snapshots"
OUT = ROOT / "analysis" / "results"

TAU_J = 0.5
TAU_C = 0.005
TOP_K = 10


def load_snapshot(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def jacc_topk(a_sorted, b_sorted, k=TOP_K):
    sa = set(a_sorted[:k]); sb = set(b_sorted[:k])
    return len(sa & sb) / max(len(sa | sb), 1)


def sorted_qubits(snap):
    rows = sorted(snap["qubits"], key=lambda r: r["readout_total"])
    return [r["q"] for r in rows], {r["q"]: r["readout_total"] for r in rows}


def parse_hours(snap, fetched_at_iso):
    """Hours between calibration (last_update) and fetch time."""
    try:
        lu = datetime.datetime.fromisoformat(snap["last_update_date"].replace("Z", "+00:00"))
        if lu.tzinfo is None:
            lu = lu.replace(tzinfo=datetime.timezone.utc)
        # fetched_at is local (naive); treat as same tz as lu if lu has offset
        ft = datetime.datetime.fromisoformat(fetched_at_iso)
        if ft.tzinfo is None and lu.tzinfo is not None:
            ft = ft.replace(tzinfo=lu.tzinfo)
        return max(0.0, (ft - lu).total_seconds() / 3600.0)
    except Exception:
        return float("nan")


def collect_epochs():
    """Group snapshots per backend into calibration epochs.
    Returns epochs: list of dicts {backend, last_update, baseline_order, baseline_cmap, pts}.
    pts = list of {hours, j10, dC_best} sorted by hours (0.0 = baseline point)."""
    epochs = []
    for back_dir in sorted(SNAP_DIR.glob("*/")):
        if back_dir.name == "calib_snapshots":
            continue
        # order snapshots by file mtime (fetch time)
        files = sorted(back_dir.glob("*.json"),
                       key=lambda f: f.stat().st_mtime)
        by_last_update = {}
        for f in files:
            try:
                snap = load_snapshot(f)
            except Exception:
                continue
            order, cmap = sorted_qubits(snap)
            lu = snap["last_update_date"]
            if lu not in by_last_update:
                by_last_update[lu] = {"backend": back_dir.name, "last_update": lu,
                                      "baseline_order": order, "baseline_cmap": cmap,
                                      "pts": []}
            e = by_last_update[lu]
            hrs = est_hours_from_mtime(f, snap)
            if not e["pts"]:
                # first snapshot after calib is the epoch baseline
                e["pts"].append({"hours": round(hrs, 3), "j10": 1.0, "dC_best": 0.0})
            else:
                j10 = jacc_topk(order, e["baseline_order"])
                dC_best = abs(cmap[e["baseline_order"][0]] - e["baseline_cmap"][e["baseline_order"][0]])
                e["pts"].append({"hours": round(hrs, 3), "j10": round(j10, 3),
                                 "dC_best": round(dC_best, 5)})
        for e in by_last_update.values():
            e["pts"].sort(key=lambda p: p["hours"])
            if len(e["pts"]) > 1:
                epochs.append(e)
    return epochs


def est_hours_from_mtime(path, snap):
    """Best-effort hours since calibration from file mtime & last_update_date."""
    try:
        lu = datetime.datetime.fromisoformat(snap["last_update_date"].replace("Z", "+00:00"))
        if lu.tzinfo is None:
            lu = lu.replace(tzinfo=datetime.timezone.utc)
        mt = datetime.datetime.fromtimestamp(path.stat().st_mtime, tz=datetime.timezone.utc)
        return max(0.0, (mt - lu).total_seconds() / 3600.0)
    except Exception:
        return float("nan")


def km_estimate(epochs):
    """Kaplan-Meier on time-to-first-failure per epoch (right-censored survival)."""
    times = []
    for e in epochs:
        pts = e["pts"]
        # failure time = hours of first point whose trigger fires
        fail_t = None
        for p in pts:
            if p["j10"] < TAU_J or p["dC_best"] > TAU_C:
                fail_t = p["hours"]
                break
        if fail_t is None and pts:
            fail_t = pts[-1]["hours"]  # censored at last observation
            times.append((fail_t, 0))  # (time, event=0 censored)
        elif fail_t is not None:
            times.append((fail_t, 1))
    times.sort()
    n = len(times)
    n_risk = n
    S = 1.0
    surv = [(0.0, 1.0)]
    i = 0
    while i < n:
        t = times[i][0]
        # count events at this exact t
        d = sum(1 for j in range(i, n) if times[j][0] == t and times[j][1] == 1)
        if n_risk > 0 and d > 0:
            S *= (1.0 - d / n_risk)
        surv.append((t, S))
        n_risk -= sum(1 for j in range(i, n) if times[j][0] == t)
        i += sum(1 for j in range(i, n) if times[j][0] == t)
    return surv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tau-j", type=float, default=0.5)
    ap.add_argument("--tau-c", type=float, default=0.005)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    global TAU_J, TAU_C
    TAU_J, TAU_C = args.tau_j, args.tau_c

    epochs = collect_epochs()
    n_backends = len({e["backend"] for e in epochs})
    n_epochs = len(epochs)
    n_snaps = sum(len(e["pts"]) for e in epochs)
    surv = km_estimate(epochs)

    median = None
    for (t0, s0), (t1, s1) in zip(surv, surv[1:]):
        if s1 <= 0.5:
            # linear interpolate crossing
            if s0 > s1:
                median = t0 + (0.5 - s0) * (t1 - t0) / (s1 - s0)
            else:
                median = t1
            break

    print(f"collected: {n_epochs} calibration epochs / {n_backends} backends / {n_snaps} snapshots")
    print(f"KM survival S(t)  (event: J10<{TAU_J} or dC_best>{TAU_C}):")
    for t, s in surv:
        print(f"  t={t:6.2f}h  S(t)={s:.3f}")
    print("median survival time =", (f"{median:.2f} h" if median is not None else "N/A (needs more data)"))

    result = {"n_epochs": n_epochs, "n_backends": n_backends, "n_snapshots": n_snaps,
              "tau_J": args.tau_j, "tau_C": args.tau_c,
              "km_curve": [{"hours": round(t, 3), "S": round(s, 4)} for t, s in surv],
              "median_survival_hours": (round(median, 3) if median is not None else None)}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "survival_analysis.json").write_text(json.dumps(result, indent=2))
    print("saved -> analysis/results/survival_analysis.json")


if __name__ == "__main__":
    main()
