"""Generate utility_model_v4.json: expand n=9 -> n>=20 via synthetic FakeMarrakesh points k=2..18"""
import json, math, random, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import numpy as np
import multi_qubit_routing as mqr
from utility_model import COLS, WEIGHT_KEYS, N_DIM, spearman_rho, fit_simplex, run_loo, run_bootstrap, j_scores, params_to_vec

RES = pathlib.Path(__file__).resolve().parent / "results"
CALIB_FILE = RES / "calib_full_e08.json"
ROUTER_ANALYSIS_FILE = RES / "router_analysis.json"
OUT = RES / "utility_model_v4.json"

# --- generate new multi points for k=2..18 (excluding 4,6,8 already in v3 but include 10,12,14,16,18)
K_NEW = [2,3,5,7,9,10,11,12,13,14,15,16,17,18]  # 14 new
# also optionally include 4,6,8 already exist -> skip duplicates, will merge

def load_existing_points():
    # reuse utility_model.load_dataset logic for single + old multi 4,6,8
    from utility_model import load_dataset
    ds = load_dataset()
    return ds["points"]

def generate_synthetic(k_vals):
    snap, rows = mqr.load_snapshot()
    backend, undirected, adj, cz_map = mqr.load_coupling_and_cz()
    mqr.load_coupling_and_cz.cache_undirected = undirected
    ranked = sorted(rows.values(), key=mqr.c_key)
    rng = random.Random(42)
    points = []
    for k in k_vals:
        print(f" Generating k={k} UniMind...", flush=True)
        res = mqr.run_one_strategy(k, "UniMind", ranked, rows, adj, cz_map, backend, rng)
        layout = res["layout"]
        vals = [rows[q] for q in layout if q in rows]
        mean_readout = sum(v["readout_total"] for v in vals)/len(vals) if vals else 0.02
        mean_sx = sum((v.get("sx_error") or 0) for v in vals)/len(vals) if vals else 0.0003
        e2q = float(res.get("est_2q_error", res.get("est_2q_additive",0)))
        e2q_log = float(res.get("E_2q_log", res.get("E_2q_log_gate",0)))
        if e2q_log==0:
            avg_cz = float(res.get("avg_cz_proxy",0.005))
            cz_cnt = int(res.get("cz_count",0))
            avg_cz = min(max(avg_cz,1e-6),0.999)
            e2q_log = cz_cnt * (-math.log(1-avg_cz)) if cz_cnt else 0.0
        e_idle = float(res.get("E_idle",0))
        if e_idle==0:
            depth = int(res.get("depth",0))
            invs=[]
            for q in layout:
                r=rows.get(q)
                if r:
                    t1=r.get("T1_us") or 100.0
                    t2=r.get("T2_us") or 100.0
                    if t1<=0: t1=100.0
                    if t2<=0: t2=100.0
                    invs.append(1/t1+1/t2)
            mean_inv = sum(invs)/len(invs) if invs else 0.02
            e_idle = depth*mean_inv
        points.append({
            "kind":"multi",
            "k":k,
            "layout":layout,
            "E_readout": float(mean_readout),
            "E_1q": float(mean_sx),
            "E_2q": float(e2q),
            "E_2q_log": float(e2q_log),
            "E_idle": float(e_idle),
            "N_SWAP": int(res.get("swap_count",0)),
            "D": int(res.get("depth",0)),
            "y": float(e2q),
            "y_label":"est_2q_error",
            "raw_metrics": {kk: res[kk] for kk in ["swap_count","cz_count","depth","est_2q_error","est_2q_additive","E_2q_log","E_idle","avg_cz_proxy","mean_inv_T"] if kk in res},
            "fallback_to_default": res.get("fallback_to_default", False),
        })
        print(f"  k={k} SWAP={res.get('swap_count')} depth={res.get('depth')} E2q={e2q:.5f} E2q_log={e2q_log:.4f} E_idle={e_idle:.4f} readout={mean_readout:.5f}", flush=True)
    return points, snap, rows

def main():
    print("Load existing n=9 points...")
    existing = load_existing_points()
    print(f" existing: {len(existing)} (k values {[p['k'] for p in existing]})")
    print(f"Generate synthetic for K_NEW={K_NEW}...")
    new_pts, snap, rows = generate_synthetic(K_NEW)
    # Merge: keep all existing (single 6 + multi 3) plus new 14
    all_points = existing + new_pts
    print(f"Merged n={len(all_points)} (existing {len(existing)} + new {len(new_pts)})")
    # Normalize features over merged set
    raw = np.array([[p[c] for c in COLS] for p in all_points], dtype=float)
    y = np.array([p["y"] for p in all_points], dtype=float)
    mins = raw.min(axis=0)
    maxs = raw.max(axis=0)
    ranges = maxs - mins
    ranges[ranges==0]=1.0
    X_norm = (raw - mins)/ranges
    scaling = {"method":"minmax","columns":COLS,"mins":{c:float(m) for c,m in zip(COLS,mins)},"maxs":{c:float(m) for c,m in zip(COLS,maxs)}}
    print(f" scaling mins {scaling['mins']}")
    print(f" scaling maxs {scaling['maxs']}")
    # Fit
    print("Full simplex fit n_samples=8000...")
    full_params, full_rho, full_p = fit_simplex(X_norm, y, n_samples=8000, seed=42)
    print(f" full rho={full_rho:.4f} p={full_p:.4f} params={full_params}")
    print("LOO n_samples=5000...")
    loo_res = run_loo(X_norm, y, n_samples=5000)
    print(f" loo_rho={loo_res['loo_rho']} mean_train={loo_res['mean_train_rho']}")
    print("Bootstrap B=200...")
    boot_res = run_bootstrap(X_norm, y, B=200, n_samples=3000, seed=123)
    print(f" boot rho mean={boot_res['spearman_dist']['mean']:.4f}")
    J_full = j_scores(X_norm, params_to_vec(full_params))
    # oob check vs old scaler: load v3 scaler and test new points would have been out-of-range
    v3 = json.loads((RES/"utility_model_v3.json").read_text())
    old_mins = np.array([v3["dataset"]["scaling"]["mins"][c] for c in COLS])
    old_maxs = np.array([v3["dataset"]["scaling"]["maxs"][c] for c in COLS])
    old_ranges = old_maxs - old_mins
    old_ranges[old_ranges==0]=1.0
    X_old_norm = (raw - old_mins)/old_ranges
    oob_any = bool(((X_old_norm<0)|(X_old_norm>1)).any())
    oob_counts = int(((X_old_norm<0)|(X_old_norm>1)).sum())
    # clipped still needed? After refit with expanded max, no clipping needed for k<=18
    clipped = np.clip(X_norm,0,1)
    # since X_norm is by definition in [0,1] for training, clipped == X_norm
    oob_new = bool(((X_norm<0)|(X_norm>1)).any())
    print(f" Old scaler OOB any={oob_any} count={oob_counts} -> v3 needed clipping: True")
    print(f" New scaler OOB any={oob_new} -> oob_clipped still needed? {oob_new}")
    # Also check holdout-style: if we used new scaler, k=18 now inside range by construction
    # Build output similar to v3 but v4
    output = {
        "version":"4.0",
        "J_definition": v3["J_definition"],
        "U_definition": v3["U_definition"],
        "dims": N_DIM,
        "columns": COLS,
        "weight_keys": WEIGHT_KEYS,
        "dataset":{
            "n_points": len(all_points),
            "n_single": 6,
            "n_multi": len(all_points)-6,
            "k_values": sorted(set(p["k"] for p in all_points)),
            "points":[
                {
                    "idx": i,
                    "kind": p["kind"],
                    "k": p["k"],
                    "layout": p["layout"],
                    "E_readout": p["E_readout"],
                    "E_1q": p["E_1q"],
                    "E_2q": p["E_2q"],
                    "E_2q_log": p["E_2q_log"],
                    "E_idle": p["E_idle"],
                    "N_SWAP": p["N_SWAP"],
                    "D": p["D"],
                    "y": p["y"],
                    "y_label": p["y_label"],
                    "X_norm": [round(float(v),6) for v in X_norm[i]],
                    "J_full": round(float(J_full[i]),6),
                } for i,p in enumerate(all_points)
            ],
            "scaling": scaling,
            "raw_feature_matrix": [[float(p[c]) for c in COLS] for p in all_points],
        },
        "full_fit":{
            "params": {k: round(float(v),4) for k,v in full_params.items()},
            "params_raw": full_params,
            "spearman": {"rho": round(float(full_rho),4), "p_value": round(float(full_p),4)},
            "ranking": [
                {"rank": i+1, "idx": int(np.argsort(J_full)[i]), "J": round(float(J_full[np.argsort(J_full)[i]]),6), "y": float(y[np.argsort(J_full)[i]])}
                for i in range(len(all_points))
            ],
        },
        "loo": loo_res,
        "bootstrap": boot_res,
        "synthetic_generation":{
            "k_new": K_NEW,
            "n_new": len(new_pts),
            "method": "FakeMarrakesh UniMind calibration-weighted SABRE, same 2026-08-29 snapshot (calib_full_e08.json), qiskit 2.5.1 transpilation opt_level=1",
            "note": "E_2q_log = cz_count * -log(1-avg_cz), E_idle = depth*mean(1/T1+1/T2), est_2q_error = 1-exp(-(cz_count*avg_cz+sum(sx)))",
        },
        "oob_analysis":{
            "old_scaler_oob_any": oob_any,
            "old_scaler_oob_count": oob_counts,
            "old_scaler_oob_clipped_needed": True,
            "new_scaler_oob_any": oob_new,
            "oob_clipped_still_needed": oob_new,
            "interpretation": "v3 scaler max D=121, E_idle=2.43 clipped k>8; v4 scaler expands to cover k<=18 so no clipping needed within expanded range; hold-out beyond k=18 would still extrapolate"
        },
        "comparison_v3":{
            "v3_n": 9,
            "v3_rho": v3["full_fit"]["spearman"]["rho"],
            "v3_p": v3["full_fit"]["spearman"]["p_value"],
            "v3_weights": v3["full_fit"]["params"],
            "v4_n": len(all_points),
            "v4_rho": round(float(full_rho),4),
            "v4_p": round(float(full_p),4),
            "v4_weights": {k: round(float(v),4) for k,v in full_params.items()},
        },
        "method": v3.get("method",{}),
    }
    # extend method notes
    output["method"]["v4_note"] = "Expanded dataset via FakeMarrakesh synthetic routing points k=2..18 (14 new UniMind), same calibration snapshot 2026-08-29, refit 7-dim J(G) with minmax over n>=20, zero quota"
    RES.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(output, indent=2))
    print(f"Saved -> {OUT}")
    # also print summary
    print(f"\n=== SUMMARY v4 ===")
    print(f" n: 9 -> {len(all_points)}")
    print(f" rho: {v3['full_fit']['spearman']['rho']} -> {full_rho:.4f}")
    print(f" p: {v3['full_fit']['spearman']['p_value']} -> {full_p:.4f}")
    print(f" weights v3 {v3['full_fit']['params']}")
    print(f" weights v4 {output['full_fit']['params']}")
    print(f" oob_clipped still needed? {oob_new}")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
