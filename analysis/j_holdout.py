"""Holdout validation for J(G) 7-dim — frozen v2.4 weights on unseen k=12/14/18.

Scientific goal: J(G) from fitting -> prediction on D_test never used in training.

Steps:
1. Load frozen scaler + weights from utility_model_v3.json (trained on k=1,4,6,8)
2. Generate D_test workloads k=12,14,18 via FakeMarrakesh + calib snapshot (same 2026-08-29)
   using multi_qubit_routing.py's UniMind pipeline (calibration-weighted SABRE)
3. Compute J_test = X_test_norm @ w_frozen (using TRAIN scaler)
4. Compute rho_test = Spearman(J_test, y_test) where y_test = est_2q_error proxy
5. Save j_holdout.json

Zero quota, local only.
"""
import json, math, pathlib, sys
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from utility_model import COLS, WEIGHT_KEYS, spearman_rho

RES = pathlib.Path(__file__).resolve().parent / "results"
SNAP_PATH = RES / "calib_full_e08.json"
TRAIN_JSON = RES / "utility_model_v3.json"
MULTI_V2_JSON = RES / "multi_qubit_routing_v2.json"
OUT_JSON = RES / "j_holdout.json"

# Import routing helpers to generate D_test on the fly (avoid re-running full benchmark if present)
import multi_qubit_routing as mqr

def load_train():
    j = json.loads(TRAIN_JSON.read_text())
    scaling = j["dataset"]["scaling"]
    full_params = j["full_fit"]["params_raw"]  # raw weights
    w = np.array([full_params[k] for k in WEIGHT_KEYS], dtype=float)
    w = w / w.sum()
    return j, scaling, w

def normalize_with_train_scaler(raw_matrix, scaling):
    mins = np.array([scaling["mins"][c] for c in COLS], dtype=float)
    maxs = np.array([scaling["maxs"][c] for c in COLS], dtype=float)
    ranges = maxs - mins
    ranges[ranges==0] = 1.0
    raw = np.array(raw_matrix, dtype=float)
    return (raw - mins) / ranges

def generate_test_points(k_vals):
    """Generate UniMind points for k in k_vals using same pipeline as multi_qubit_routing.py v2."""
    import random
    snap, rows = mqr.load_snapshot()
    backend, undirected, adj, cz_map = mqr.load_coupling_and_cz()
    mqr.load_coupling_and_cz.cache_undirected = undirected
    ranked = sorted(rows.values(), key=mqr.c_key)
    rng = random.Random(42)
    # Build UniMind layouts for each k (reuse internal helpers)
    # We call the high-level benchmark for those k only, with minimal trials for speed
    # To avoid recomputing all k, we directly call per-k logic
    test_points = []
    for k in k_vals:
        print(f"  Generating k={k} via UniMind weighted SABRE...")
        res = mqr.run_one_strategy(k, "UniMind", ranked, rows, adj, cz_map, backend, rng)
        uni = res
        if uni is None:
            print(f"    WARN: no UniMind result for k={k}, skipping")
            continue
        layout = uni.get("layout") or uni.get("layout_median") or uni.get("best_layout")
        vals = [rows[q] for q in layout if q in rows]
        mean_readout = sum(v["readout_total"] for v in vals)/len(vals) if vals else 0.02
        mean_sx = sum((v.get("sx_error") or 0) for v in vals)/len(vals) if vals else 0.0003
        e2q = float(uni.get("est_2q_error", uni.get("est_2q_additive", 0)))
        e2q_log = float(uni.get("E_2q_log", uni.get("E_2q_log_gate", 0)))
        if e2q_log==0:
            avg_cz = float(uni.get("avg_cz_proxy", 0.005))
            cz_cnt = int(uni.get("cz_count", 0))
            avg_cz = min(max(avg_cz, 1e-6), 0.999)
            e2q_log = cz_cnt * (-math.log(1-avg_cz)) if cz_cnt else 0.0
        e_idle = float(uni.get("E_idle", 0))
        if e_idle==0:
            depth = int(uni.get("depth", 0))
            invs = []
            for q in layout:
                r = rows.get(q)
                if r:
                    t1 = r.get("T1_us") or 100.0
                    t2 = r.get("T2_us") or 100.0
                    if t1<=0: t1=100.0
                    if t2<=0: t2=100.0
                    invs.append(1/t1+1/t2)
            mean_inv = sum(invs)/len(invs) if invs else 0.02
            e_idle = depth * mean_inv
        test_points.append({
            "k": k,
            "layout": layout,
            "E_readout": float(mean_readout),
            "E_1q": float(mean_sx),
            "E_2q": float(e2q),
            "E_2q_log": float(e2q_log),
            "E_idle": float(e_idle),
            "N_SWAP": int(uni.get("swap_count", 0)),
            "D": int(uni.get("depth", 0)),
            "y": float(e2q),
            "raw_metrics": uni,
        })
        print(f"    k={k} layout {layout[:6]}... SWAP {uni.get('swap_count')} depth {uni.get('depth')} E2q {e2q:.5f} E2q_log {e2q_log:.4f} E_idle {e_idle:.4f}")
    return test_points

def main():
    print("=== J(G) Holdout Validation ===")
    train_j, scaling, w = load_train()
    print(f"Train: n={train_j['dataset']['n_points']} k={train_j['dataset']['k_values']} rho_full={train_j['full_fit']['spearman']['rho']} p={train_j['full_fit']['spearman']['p_value']}")
    print(f"Frozen weights: {dict(zip(WEIGHT_KEYS, [round(float(v),4) for v in w]))}")
    print(f"Scaler mins: {scaling['mins']}")
    print(f"Scaler maxs: {scaling['maxs']}")

    k_test = [12,14,18]
    test_pts = generate_test_points(k_test)
    if not test_pts:
        print("No test points generated, abort")
        return 1
    raw_mat = [[p[c] for c in COLS] for p in test_pts]
    X_test_norm = normalize_with_train_scaler(raw_mat, scaling)
    # Clip to [0,1] with note if out-of-range (extrapolation)
    clipped = np.clip(X_test_norm, 0, 1)
    oob = (X_test_norm < 0) | (X_test_norm > 1)
    if oob.any():
        print(f"WARN: {oob.sum()} feature values out of train [0,1] range (extrapolation) — clipped for J scoring but reported")
        print(f"  raw X_test_norm min {X_test_norm.min(axis=0).round(3)} max {X_test_norm.max(axis=0).round(3)}")
    y_test = np.array([p["y"] for p in test_pts], dtype=float)
    J_test = X_test_norm @ w  # use unclipped for rho, but clipped variant also reported
    J_test_clipped = clipped @ w
    rho, p = spearman_rho(J_test.tolist(), y_test.tolist())
    rho_c, p_c = spearman_rho(J_test_clipped.tolist(), y_test.tolist())
    print(f"\nHoldout result (k={k_test}):")
    for i,pnt in enumerate(test_pts):
        print(f"  k={pnt['k']} J={J_test[i]:.4f} J_clipped={J_test_clipped[i]:.4f} y={pnt['y']:.5f} layout={pnt['layout']}")
    print(f"  rho_test (unclipped) = {rho:.4f} p={p:.4f}")
    print(f"  rho_test (clipped)   = {rho_c:.4f} p={p_c:.4f}")
    print(f"  n_test={len(test_pts)}")

    # Also compute Utility win: compare UniMind vs Default vs Random on same k_test
    # Reuse benchmark results for those k
    print("\nUtility comparison on D_test (same k):")
    import random as _rnd2
    snap2, rows2 = mqr.load_snapshot()
    backend2, undirected2, adj2, cz_map2 = mqr.load_coupling_and_cz()
    mqr.load_coupling_and_cz.cache_undirected = undirected2
    ranked2 = sorted(rows2.values(), key=mqr.c_key)
    rng2 = _rnd2.Random(42)
    for k in k_test:
        for strat in ["Random","Default","UniMind"]:
            uni = mqr.run_one_strategy(k, strat, ranked2, rows2, adj2, cz_map2, backend2, rng2)
            if not uni: continue
            e2q_log = float(uni.get("E_2q_log", 0))
            print(f"  k={k} {strat:12s} SWAP {uni.get('swap_count'):3d} depth {uni.get('depth'):3d} E2q {uni.get('est_2q_error',0):.5f} E2q_log {e2q_log:.3f}")

    out = {
        "train": {
            "n": train_j["dataset"]["n_points"],
            "k_values": train_j["dataset"]["k_values"],
            "full_rho": train_j["full_fit"]["spearman"]["rho"],
            "full_p": train_j["full_fit"]["spearman"]["p_value"],
            "weights": {k: float(v) for k,v in zip(WEIGHT_KEYS, w)},
            "scaling": scaling,
        },
        "test": {
            "k_values": k_test,
            "n_test": len(test_pts),
            "points": [
                {
                    "k": p["k"],
                    "layout": p["layout"],
                    "features": {c: p[c] for c in COLS},
                    "y": p["y"],
                    "J": float(J_test[i]),
                    "J_clipped": float(J_test_clipped[i]),
                    "X_norm": [float(v) for v in X_test_norm[i]],
                    "X_norm_clipped": [float(v) for v in clipped[i]],
                } for i,p in enumerate(test_pts)
            ],
            "rho": round(float(rho),4),
            "p_value": round(float(p),4),
            "rho_clipped": round(float(rho_c),4),
            "p_clipped": round(float(p_c),4),
            "oob_clipped": bool(oob.any()),
        },
        "interpretation": "Holdout uses frozen train scaler+weights; rho_test measures generalization to larger k. If rho_test<0.6 or p>0.05, J(G) is not yet a validated decision model.",
        "method": "FakeMarrakesh 2026-08-29 snapshot, same UniMind weighted SABRE pipeline, zero quota",
    }
    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\nSaved -> {OUT_JSON}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
