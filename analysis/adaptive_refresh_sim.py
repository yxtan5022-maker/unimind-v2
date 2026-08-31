"""
P0#1 + P0#2: Unified Adaptive-Refresh mechanism simulation.

Simulates a runtime processing a stream of jobs while device calibration drifts daily,
calibrated to the REAL D0/D1/D2 drift statistics. Compares, on a UNIFIED timeline:
    P1 Static   (never refresh)
    P2 Periodic (every delta h)
    P3 Adaptive (trigger: Jaccard<tau_J OR dC>tau_C)

Metrics per policy, from the SAME simulation:
    - Fidelity   = fraction of jobs whose placement stays within tolerance
    - Refresh overhead = number of snapshot fetches/scoring passes (cost)
    - false refresh = refresh fired that did NOT change the top-10/best choice
    - missed drift  = ranking shifted but trigger did not fire
    - total utility/cost  = a scalar combining fidelity and refresh cost

Also performs the threshold sensitivity sweep (P0#2): tau_J x tau_C over the Monte Carlo,
reporting false/missed/effective operating points and the knee of the frontier.

Everything is a self-contained simulation; zero QPU. Drift calibrated to committed snapshots.
"""
import json
from pathlib import Path
import numpy as np

ROOT = Path(r"C:\Users\SCSM11\Desktop\unimind-v2")
DRIFT = ROOT / "data" / "drift"
OUT = ROOT / "analysis" / "results"
OUT.mkdir(parents=True, exist_ok=True)

def load(path):
    return {q["q"]: q["readout_total"] for q in json.load(open(path))["qubits"]}

D0 = load(DRIFT / "calib_2026-08-29.json")
D1 = load(DRIFT / "calib_2026-08-30.json")
D2 = load(DRIFT / "calib_2026-08-31.json")

# --- Calibrated drift model from real D0->D1 / D1->D2 transitions ---
dC_01 = np.array([D1[q] - D0[q] for q in D0])
dC_12 = np.array([D2[q] - D1[q] for q in D1])
# pool empirical per-qubit daily drifts
all_dC = np.concatenate([dC_01, dC_12])
emp_mean = all_dC.mean()
emp_std = all_dC.std()
emp_scale = np.median(np.abs(all_dC - emp_mean)) * 1.4826  # robust sigma

# A single "day" of drift: add empirical-calibrated noise to every qubit's C
def drift_day(C, rng, sigma=1.0):
    # lognormal-ish heavy tail like real data (q37 jumped 0.64)
    arr = np.array(list(C.values())) if isinstance(C, dict) else np.asarray(C)
    n = arr.size
    # bg: most qubits small; rare large "burst" jumps like q37
    bg = rng.normal(emp_mean, emp_scale, size=n)
    burst_mask = rng.random(n) < 0.02          # ~2% qubits get a burst (q37-like)
    burst = rng.exponential(0.15, size=n) * burst_mask
    delta = bg + burst * sigma
    return np.clip(arr + delta, 1e-4, 1.0)

C0 = np.array([D0[q] for q in sorted(D0)])

# E2E fidelity model: a winner (best-k qubits) passes if its C stays below threshold.
# Calibrate: fresh pins from best qubit → 70% pass (21/30); stale 24h → 37% (11/30).
# We model per-job pass probability p_pass = clamp(1 - best_C / 0.02, 0.05, 0.95)
# so fresh best_C~0.0066 → ~0.67; stale best_C~0.0139 → ~0.31; in range of measured.
def pass_prob(best_C):
    return float(np.clip(1.0 - best_C / 0.02, 0.05, 0.95))

def top_k_jacc(Ca, Cb, k=10):
    a = set(np.argsort(Ca)[:k])
    b = set(np.argsort(Cb)[:k])
    return len(a & b) / max(len(a | b), 1)

def run_simulation(policy, N_DAYS=30, jobs_per_day=20, tau_J=0.5, tau_C=0.005,
                   delta_h=24, seed=0):
    rng = np.random.default_rng(seed)
    n = len(C0)
    C = C0.copy()                      # true device state (unknown to scheduler)
    stored = C0.copy()                 # scheduler's snapshot
    stored_day = 0
    results = {"jobs": 0, "pass": 0, "refreshes": 0, "score_passes": 0,
               "false_refresh": 0, "missed_drift": 0, "drift_events": 0}
    top10_prev = set(np.argsort(stored)[:10])

    STEP_H = 6                          # simulation resolution: 6-hour steps
    steps = N_DAYS * (24 // STEP_H)     # 4 steps/day
    jobs_per_step = max(1, jobs_per_day // (24 // STEP_H))

    # drift happens once per 24h (calibration cycle); within a day it is stable
    last_drift_kind = 0
    for step in range(1, steps + 1):
        day_num = (step * STEP_H) // 24   # which 24h bucket
        at_calib = (step * STEP_H) % 24 == 0   # end of a 24h cycle -> fresh calibration

        if at_calib:
            C = drift_day(C, rng)

        # periodic: refresh every delta_h hours
        fired = False
        if policy.startswith("periodic") and (step * STEP_H) % delta_h == 0:
            stored = C.copy(); stored_day = day_num
            results["refreshes"] += 1
            results["score_passes"] += 1
            fired = True
        # adaptive
        elif policy == "adaptive":
            jac = top_k_jacc(stored, C)
            dC = np.abs(C[np.argmin(stored)] - stored[np.argmin(stored)])
            if (jac < tau_J) or (dC > tau_C):
                fired = True
                results["score_passes"] += 1
                results["refreshes"] += 1
                if set(np.argsort(stored)[:10]) == top10_prev:
                    results["false_refresh"] += 1
                stored = C.copy(); stored_day = day_num
            else:
                results["score_passes"] += 1
        # static: never fires

        # ground-truth needed refresh: top-10 changed since last refresh
        needed = set(np.argsort(stored)[:10]) != set(np.argsort(C)[:10])
        if needed:
            results["missed_drift"] += 1 if not fired else 0

        # jobs placed using stored snapshot, executed on true state C
        for _ in range(jobs_per_step):
            results["jobs"] += 1
            best_idx = np.argmin(stored)
            results["pass"] += 1 if rng.random() < pass_prob(C[best_idx]) else 0

        if at_calib:
            top10_prev = set(np.argsort(C)[:10])

    r = results
    return {
        "fidelity": r["pass"] / r["jobs"],
        "n_jobs": r["jobs"],
        "n_refresh": r["refreshes"],
        "score_passes": r["score_passes"],
        "false_refresh": r["false_refresh"],
        "missed_drift": r["missed_drift"],
        "refresh_rate": r["refreshes"] / N_DAYS,       # per day
        "overhead_over_refresh": r["score_passes"],
    }

# --- P0#1 unified comparison ---
print("=== P0#1: Static vs Periodic vs Adaptive (30 simulated days, 20 jobs/day) ===")
print(f"{'policy':<22}{'fidelity':>9}{'refresh/day':>11}{'scorepass':>10}{'false':>7}{'missed':>8}")
policies = [("static", dict()), ("periodic_6h", dict(delta_h=6)),
            ("periodic_12h", dict(delta_h=12)), ("periodic_24h", dict(delta_h=24)),
            ("periodic_48h", dict(delta_h=48)), ("adaptive", dict())]
summary = {}
for name, kw in policies:
    res = run_simulation(name, **kw)
    summary[name] = res
    print(f"{name:<22}{res['fidelity']:>9.3f}{res['refresh_rate']:>11.2f}"
          f"{res['score_passes']:>10}{res['false_refresh']:>7}{res['missed_drift']:>8}")

# --- P0#2 threshold sensitivity over MC ---
print("\n=== P0#2: Threshold sensitivity (tau_J x tau_C), same MC ===")
tau_Js = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
tau_Cs = [0.002, 0.005, 0.008, 0.012, 0.02]
sweep = []
for tj in tau_Js:
    for tc in tau_Cs:
        res = run_simulation("adaptive", tau_J=tj, tau_C=tc)
        # effective refresh cost: refreshes + score passes (scoring is ~0.04ms, negligible; count fetches)
        util = res["fidelity"] - 0.005 * res["refresh_rate"] - 0.002 * (res["missed_drift"] > 0)
        sweep.append({"tau_J": tj, "tau_C": tc, "fidelity": round(res["fidelity"], 4),
                      "refresh_per_day": round(res["refresh_rate"], 4),
                      "false": res["false_refresh"], "missed": res["missed_drift"],
                      "effective_util": round(util, 4)})
# print a compact grid: fidelity at each (tau_J, tau_C)
print("fidelity grid (rows tau_J, cols tau_C):")
hdr = "tau_J\\tau_C" + "".join(f"{tc:>9.3f}" for tc in tau_Cs)
print(hdr)
for i, tj in enumerate(tau_Js):
    row = [f"{tj:>10.2f}"] + [f"{r['fidelity']:>9.3f}" for r in sweep if abs(r['tau_J']-tj)<1e-9]
    print("".join(row))

# Knee analysis: Pareto frontier of (refresh_rate, fidelity)
print("\nPareto frontier (refresh_rate, fidelity) — knee = default (0.5,0.005)?")
by_rf = {}
for r in sweep:
    k = round(r["refresh_per_day"], 3)
    if k not in by_rf or r["fidelity"] > by_rf[k]:
        by_rf[k] = r["fidelity"]
for k in sorted(by_rf):
    print(f"  refresh/day {k:.3f} -> max fidelity {by_rf[k]:.3f}")

out = {"calibration": {"emp_mean_dC": round(float(emp_mean), 5),
                       "emp_robust_sigma": round(float(emp_scale), 5),
                       "burst_prob": 0.02, "burst_scale": 0.15},
       "policies": summary,
       "threshold_sweep": sweep}
(OUT / "adaptive_refresh_simulation.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
print("\nsaved -> analysis/results/adaptive_refresh_simulation.json")
