"""
Phase 4/5: Offline refresh policy comparison and threshold sweep.
Uses D0/D1/D2 snapshots + existing E2E data.
Zero QPU cost — all simulation.
"""
import json, sys
from pathlib import Path
from collections import defaultdict
import numpy as np

ROOT = Path(r"C:\Users\SCSM11\Desktop\unimind-v2")
DRIFT = ROOT / "data" / "drift"
E2E = ROOT / "data" / "e2e"
OUT = ROOT / "analysis" / "results"
OUT.mkdir(parents=True, exist_ok=True)

# --- Load snapshots ---
def load_snapshot(path):
    with open(path) as f:
        data = json.load(f)
    qubits = {}
    for q in data["qubits"]:
        qubits[q["q"]] = {
            "C": q["readout_total"],
            "p01": q["p01"],
            "p10": q["p10"],
            "T1": q.get("T1_us", 0),
            "T2": q.get("T2_us", 0),
            "sx": q.get("sx_error", 0),
        }
    return {
        "backend": data["backend"],
        "update": data["last_update_date"],
        "fetched": data["fetched_at"],
        "qubits": qubits,
    }

print("Loading snapshots...")
D0 = load_snapshot(DRIFT / "calib_2026-08-29.json")
D1 = load_snapshot(DRIFT / "calib_2026-08-30.json")
D2 = load_snapshot(DRIFT / "calib_2026-08-31.json")
snapshots = [D0, D1, D2]
snap_names = ["D0", "D1", "D2"]
snap_hours = [0, 24, 34]  # approximate hours from D0

print(f"  D0: {len(D0['qubits'])} qubits, D1: {len(D1['qubits'])} qubits, D2: {len(D2['qubits'])} qubits")

# --- Pairwise stability ---
def spearman_rank_corr(x, y):
    """Spearman rho via Pearson on ranks."""
    from scipy.stats import spearmanr
    rho, p = spearmanr(list(x), list(y))
    return rho, p

def top_k_jaccard(qubits_a, qubits_b, k=10):
    top_a = set(sorted(qubits_a, key=lambda q: qubits_a[q])[:k])
    top_b = set(sorted(qubits_b, key=lambda q: qubits_b[q])[:k])
    return len(top_a & top_b) / len(top_a | top_b)

def top_k_overlap(qubits_a, qubits_b, k=10):
    top_a = set(sorted(qubits_a, key=lambda q: qubits_a[q])[:k])
    top_b = set(sorted(qubits_b, key=lambda q: qubits_b[q])[:k])
    return len(top_a & top_b)

print("\n--- Pairwise Stability Matrix ---")
stability = {}
for i in range(len(snapshots)):
    for j in range(len(snapshots)):
        if i == j:
            continue
        qi = {q: snapshots[i]["qubits"][q]["C"] for q in snapshots[i]["qubits"]}
        qj = {q: snapshots[j]["qubits"][q]["C"] for q in snapshots[j]["qubits"]}
        common = sorted(set(qi) & set(qj))
        rho, p = spearman_rank_corr([qi[q] for q in common], [qj[q] for q in common])
        j3 = top_k_jaccard(qi, qj, 3)
        j5 = top_k_jaccard(qi, qj, 5)
        j10 = top_k_jaccard(qi, qj, 10)
        stability[f"{snap_names[i]}->{snap_names[j]}"] = {
            "spearman": round(rho, 4),
            "p_value": round(p, 6),
            "jaccard_3": round(j3, 4),
            "jaccard_5": round(j5, 4),
            "jaccard_10": round(j10, 4),
        }
        print(f"  {snap_names[i]}->{snap_names[j]}: rho={rho:.4f} J@3={j3:.4f} J@5={j5:.4f} J@10={j10:.4f}")

# --- Staleness cost model ---
# For each snapshot pair, compute: what happens if we pin from the OLD snapshot
# and execute on the NEW device state?
def staleness_cost(pin_snap, exec_snap, k_values=[6]):
    """Simulate staleness by comparing C(q) of pinned qubits on exec snapshot."""
    pin_qs = {q: pin_snap["qubits"][q]["C"] for q in pin_snap["qubits"]}
    exec_qs = {q: exec_snap["qubits"][q]["C"] for q in exec_snap["qubits"]}
    common = sorted(set(pin_qs) & set(exec_qs))

    # Best-k from pin snapshot
    best_k = sorted(common, key=lambda q: pin_qs[q])[:max(k_values)]

    # C values of those qubits on exec snapshot (stale)
    stale_C = [exec_qs[q] for q in best_k]
    # Best-k if we had chosen fresh from exec snapshot
    fresh_k = sorted(common, key=lambda q: exec_qs[q])[:max(k_values)]
    fresh_C = [exec_qs[q] for q in fresh_k]

    return {
        "stale_mean_C": np.mean(stale_C),
        "fresh_mean_C": np.mean(fresh_C),
        "ratio": np.mean(stale_C) / max(np.mean(fresh_C), 1e-10),
        "stale_top3_C": stale_C[:3],
        "fresh_top3_C": fresh_C[:3],
    }

print("\n--- Staleness Cost ---")
stale_costs = {}
for i in range(len(snapshots)):
    for j in range(len(snapshots)):
        if i == j:
            continue
        key = f"{snap_names[i]}_pin_on_{snap_names[j]}"
        cost = staleness_cost(snapshots[i], snapshots[j])
        stale_costs[key] = {k: round(v, 4) if isinstance(v, float) else v
                           for k, v in cost.items()}
        print(f"  {key}: stale_mean={cost['stale_mean_C']:.4f} fresh_mean={cost['fresh_mean_C']:.4f} ratio={cost['ratio']:.2f}x")

# --- Refresh trigger simulation ---
def check_trigger(stored_snap, current_snap, tau_J=0.5, tau_C=0.005):
    """Check if refresh trigger fires."""
    stored_qs = {q: stored_snap["qubits"][q]["C"] for q in stored_snap["qubits"]}
    current_qs = {q: current_snap["qubits"][q]["C"] for q in current_snap["qubits"]}
    common = set(stored_qs) & set(current_qs)

    # Jaccard on top-10
    top_stored = set(sorted(common, key=lambda q: stored_qs[q])[:10])
    top_current = set(sorted(common, key=lambda q: current_qs[q])[:10])
    jaccard = len(top_stored & top_current) / max(len(top_stored | top_current), 1)

    # Best qubit C change
    best_q = min(common, key=lambda q: stored_qs[q])
    delta_C = current_qs[best_q] - stored_qs[best_q]

    fired = (jaccard < tau_J) or (abs(delta_C) > tau_C)
    return {
        "jaccard": round(jaccard, 4),
        "delta_C": round(delta_C, 6),
        "fired": fired,
    }

# --- Policy simulation ---
print("\n--- Policy Simulation ---")
policies = {}

# P1: Static (never refresh)
policies["P1_static"] = {
    "name": "Static (never refresh)",
    "refreshes": 0,
    "snapshots_used": ["D0"],
    "frozen_pass": 11,  # from E2E data
    "refresh_pass": None,
}

# P2: Periodic (various intervals)
for delta_h in [6, 12, 24, 48]:
    # With D0-D1-D2 spanning 0-34h, periodic-6h would refresh at 6,12,18,24,30
    # But we only have 3 snapshots, so simulate what WOULD happen
    refresh_times = list(range(delta_h, 35, delta_h))
    # Map to nearest snapshot
    snap_map = {0: 0, 24: 1, 34: 2}
    used_snaps = []
    for rt in refresh_times:
        nearest = min(snap_map.keys(), key=lambda t: abs(t - rt))
        used_snaps.append(snap_names[snap_map[nearest]])
    policies[f"P2_periodic_{delta_h}h"] = {
        "name": f"Periodic (every {delta_h}h)",
        "refreshes": len(refresh_times),
        "snapshots_used": used_snaps,
    }

# P3: Adaptive (default trigger)
trigger_result = check_trigger(D0, D1)
policies["P3_adaptive"] = {
    "name": "Adaptive (J<0.5 or dC>0.005)",
    "trigger_result_D0_D1": trigger_result,
    "refreshes": 1 if trigger_result["fired"] else 0,
    "snapshots_used": ["D0", "D1"] if trigger_result["fired"] else ["D0"],
}

for name, pol in policies.items():
    print(f"  {pol['name']}: {pol['refreshes']} refreshes")
    if "trigger_result_D0_D1" in pol:
        tr = pol["trigger_result_D0_D1"]
        print(f"    trigger: jaccard={tr['jaccard']:.4f} delta_C={tr['delta_C']:.6f} fired={tr['fired']}")

# --- Threshold sweep (Phase 5) ---
print("\n--- Threshold Sweep ---")
sweep_results = []
for tau_J in np.arange(0.1, 1.0, 0.05):
    for tau_C in [0.001, 0.002, 0.003, 0.005, 0.008, 0.01, 0.015, 0.02]:
        result = check_trigger(D0, D1, tau_J=tau_J, tau_C=tau_C)
        # Estimate: if trigger fires at D0->D1, we'd refresh to D1
        # If not, we stay on D0 (stale)
        # Fidelity proxy: fresh pins pass 21/30, stale pass 11/30 (from E2E)
        if result["fired"]:
            fidelity_proxy = 21 / 30  # would refresh -> fresh pins
            refresh_count = 1
        else:
            fidelity_proxy = 11 / 30  # stay stale
            refresh_count = 0
        sweep_results.append({
            "tau_J": round(float(tau_J), 3),
            "tau_C": tau_C,
            "jaccard": result["jaccard"],
            "delta_C": result["delta_C"],
            "fired": result["fired"],
            "refresh_count": refresh_count,
            "fidelity_proxy": round(fidelity_proxy, 4),
        })

print(f"  {len(sweep_results)} threshold combinations tested")
fired_count = sum(1 for r in sweep_results if r["fired"])
print(f"  {fired_count}/{len(sweep_results)} triggered refresh")

# --- T_valid estimation ---
print("\n--- T_valid Estimation ---")
# From D0->D1: stale top-3 worst pin is 2.1x worse
# From D0->D2: need to check
cost_01 = staleness_cost(D0, D1)
cost_02 = staleness_cost(D0, D2)
cost_12 = staleness_cost(D1, D2)

t_valid_estimate = {
    "D0_to_D1_24h": {
        "stale_mean_C": round(cost_01["stale_mean_C"], 4),
        "fresh_mean_C": round(cost_01["fresh_mean_C"], 4),
        "ratio": round(cost_01["ratio"], 2),
    },
    "D0_to_D2_34h": {
        "stale_mean_C": round(cost_02["stale_mean_C"], 4),
        "fresh_mean_C": round(cost_02["fresh_mean_C"], 4),
        "ratio": round(cost_02["ratio"], 2),
    },
    "D1_to_D2_10h": {
        "stale_mean_C": round(cost_12["stale_mean_C"], 4),
        "fresh_mean_C": round(cost_12["fresh_mean_C"], 4),
        "ratio": round(cost_12["ratio"], 2),
    },
    "note": "T_valid lower bound: ratio > 2x at 24h suggests T_valid < 24h for k=6 placement",
}
for k, v in t_valid_estimate.items():
    if isinstance(v, dict):
        print(f"  {k}: ratio={v.get('ratio', 'N/A')}x")
    else:
        print(f"  {k}: {v}")

# --- Save all results ---
output = {
    "stability_matrix": stability,
    "staleness_cost": stale_costs,
    "policies": policies,
    "threshold_sweep": sweep_results,
    "t_valid_estimate": t_valid_estimate,
    "data_source": {
        "D0": "calib_2026-08-29.json",
        "D1": "calib_2026-08-30.json",
        "D2": "calib_2026-08-31.json",
    },
    "e2e_evidence": {
        "frozen_full_pass": 11,
        "frozen_ablated_pass": 12,
        "refresh_full_pass": 21,
        "refresh_ablated_pass": 23,
        "n_per_arm": 30,
    },
}

out_path = OUT / "refresh_policy_analysis.json"
with open(out_path, "w") as f:
    json.dump(output, f, indent=2, default=str)
print(f"\nSaved to {out_path}")
print("Done.")
