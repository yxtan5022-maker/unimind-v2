"""
Publication-quality plots for the intra-day micro-drift + survival story.

Reads data/calib_snapshots/telemetry_log.jsonl (one row per pull, per backend)
and emits vector figures (PDF). Designed to run the moment 5-7 days of crawler
data exist; harmless to run on sparse data (it just shows what it has).

Figures:
  fig1_intraday_jaccard.pdf  -- top-1/3/10 Jaccard vs post-calibration baseline
                                as a function of hours since calibration, one
                                line per backend (the "queue-wait-scale expiry"
                                evidence).
  fig2_survival_km.pdf       -- Kaplan-Meier survival curve with median survival
                                time marker (the derived refresh operating point).

Event definition (mirrors survival_analysis.py): J10 < tau_J OR best-dC > tau_C
within an epoch relative to that epoch's post-calibration baseline.
"""
import argparse
import collections
import datetime
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(r"C:\Users\SCSM11\Desktop\unimind-v2")
LOG = ROOT / "data" / "calib_snapshots" / "telemetry_log.jsonl"
OUT = ROOT / "analysis" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

TAU_J = 0.5
TAU_C = 0.005
THRESHOLD_DASH = 0.5


def load_rows():
    rows = []
    for line in LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    return rows


def hours(row):
    return row.get("hours_since_calib")


def fig1_intraday_jaccard(rows):
    by_back = collections.defaultdict(list)
    for r in rows:
        by_back[r["backend"]].append(r)
    fig, ax = plt.subplots(figsize=(6, 3.4))
    pm = {"ibm_marrakesh": "#1f77b4", "ibm_kingston": "#d62728", "ibm_fez": "#2ca02c"}
    for b, rs in sorted(by_back.items()):
        rs = sorted(rs, key=lambda r: hours(r))
        hs = [hours(r) for r in rs]
        ax.plot(hs, [r["jacc_top10"] for r in rs], "o-",
                label=b, color=pm.get(b, None), markersize=3, lw=1.4)
    ax.axhline(THRESHOLD_DASH, color="gray", ls="--", lw=1,
               label=f"trigger J$_{{10}}={THRESHOLD_DASH}$")
    ax.set_xlabel("hours since calibration")
    ax.set_ylabel("top-10 Jaccard vs post-calib baseline")
    ax.set_ylim(0, 1.05)
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "fig1_intraday_jaccard.pdf")
    plt.close(fig)
    print("wrote", OUT / "fig1_intraday_jaccard.pdf")


def km_over_rows(rows):
    """Kaplan-Meier over time-to-first-trigger per (backend, calibration epoch)."""
    by_epoch = collections.defaultdict(list)   # (backend,last_update) -> pts sorted by hours
    for r in rows:
        key = (r["backend"], r["last_update"])
        by_epoch[key].append(r)
    times = []
    for (b, lu), rs in by_epoch.items():
        rs = sorted(rs, key=hours)
        fail_t = None
        for idx, r in enumerate(rs):
            # first point after baseline that trips the trigger
            if idx > 0 and (r["jacc_top10"] < TAU_J):
                fail_t = hours(r)
                break
        if fail_t is None and rs:
            times.append((hours(rs[-1]), 0))   # censored
        elif fail_t is not None:
            times.append((fail_t, 1))
    times.sort()
    n = len(times)
    surv = [(0.0, 1.0)]
    S = 1.0
    n_risk = n
    i = 0
    while i < n:
        t = times[i][0]
        d = sum(1 for j in range(i, n) if times[j][0] == t and times[j][1] == 1)
        if d and n_risk > 0:
            S *= 1.0 - d / n_risk
        surv.append((t, S))
        n_risk -= sum(1 for j in range(i, n) if times[j][0] == t)
        i += sum(1 for j in range(i, n) if times[j][0] == t)
    median = None
    for (t0, s0), (t1, s1) in zip(surv, surv[1:]):
        if s1 <= 0.5 and s0 > s1:
            median = t0 + (0.5 - s0) * (t1 - t0) / (s1 - s0)
            break
    return surv, median


def fig2_survival_km(rows):
    surv, median = km_over_rows(rows)
    fig, ax = plt.subplots(figsize=(5.6, 3.4))
    hh = [t for t, _ in surv]
    ss = [s for _, s in surv]
    ax.step(hh, ss, where="post", color="#1f77b4", lw=2)
    ax.axhline(0.5, color="gray", ls="--", lw=1)
    if median is not None:
        ax.axvline(median, color="#d62728", ls="--", lw=1.2)
        ax.annotate(f"median {median:.1f} h", xy=(median, 0.5),
                    xytext=(median + 0.3, 0.45), fontsize=8, color="#d62728")
    ax.set_xlabel("hours since calibration (survival time)")
    ax.set_ylabel("P(snapshot still valid)")
    ax.set_ylim(-0.03, 1.05)
    ax.grid(alpha=0.3)
    title = f"KM survival, {len(surv)-1} event(s)"
    if median is not None:
        title += f", median {median:.1f} h"
    ax.set_title(title, fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / "fig2_survival_km.pdf")
    plt.close(fig)
    print("wrote", OUT / "fig2_survival_km.pdf", "| median:", median)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fig", default="both", choices=["both", "jaccard", "km"])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rows = load_rows()
    if args.fig in ("both", "jaccard"):
        fig1_intraday_jaccard(rows)
    if args.fig in ("both", "km"):
        surv, median = km_over_rows(rows)
        fig2_survival_km(rows)
        if args.json:
            import sys
            json.dump({"km": [{"h": t, "S": s} for t, s in surv],
                       "median_hours": median}, sys.stdout)
    n_back = len({r["backend"] for r in rows})
    print(f"{len(rows)} pull rows / {n_back} backends")


if __name__ == "__main__":
    main()
