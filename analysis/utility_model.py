"""Reliability-aware utility model v3 — 7-dim J(G) + SOTA features E_2q_log & E_idle.

J(G) = alpha*E_readout + beta*E_1q + gamma*E_2q + gamma_log*E_2q_log + eta_idle*E_idle + delta*N_SWAP + lambda_*D
U(P) = P_success - lambda1*L - lambda2*C - lambda3*E  (kept for docs)

v3 changes vs v2:
  1) J(G) 扩展为 7 维：新增 E_2q_log = Σ -log(1 - cz_error) (SOTA 2606.12816, cost(edge)=-log(1-p2q))
     和 E_idle = depth * mean(1/T1+1/T2) (SOTA 2405.18785, idle decoherence proxy)。
     两者均在 multi_qubit_routing.py v3 中已计算并持久化到 multi_qubit_routing_v2.json。
  2) calibration snapshot 读取显式包含 T1/T2（load_snapshot 补齐缺失值），E_idle 依赖它。
  3) Fitting via full_fit + LOO-CV + bootstrap over 7-simplex Dirichlet sampling。
     输出 utility_model_v3.json (zero quota, local only)。保留 v2 产物不动。

Dataset = 6 stratified single-qubit points (E_2q=0,E_2q_log=0,N_SWAP=0,D=2, y=max_dev)
        + 3 multi-qubit UniMind aggregates (k=4,6,8, y=est_2q_error proxy) with all 7 features.
All features min-max normalized before weighting.

References:
  - analysis/results/calib_full_e08.json  (IBM Marrakesh snapshot, now T1/T2 required)
  - analysis/results/router_analysis.json (6 stratified qubits, max_dev)
  - analysis/results/multi_qubit_routing_v2.json (k=4/6/8 SWAP/depth/CZ/E_2q_log/E_idle)
"""
from __future__ import annotations
import json
import math
import random
from pathlib import Path
from typing import Any

import numpy as np

RES = Path(__file__).resolve().parent / "results"
ROOT_RES = Path(__file__).resolve().parent.parent / "results"
CALIB_FILE = RES / "calib_full_e08.json"
ROUTER_ANALYSIS_FILE = RES / "router_analysis.json"
# v3 primary multi file (now contains E_2q_log/E_idle); fallback to legacy
MULTI_FILE_V2 = RES / "multi_qubit_routing_v2.json"
MULTI_FILE_LEGACY = RES / "multi_qubit_routing.json"
OUTPUT_FILE = RES / "utility_model_v3.json"
OUTPUT_FILE_ROOT = ROOT_RES / "utility_model_v3.json"
LEGACY_V2_OUTPUT = RES / "utility_model_v2.json"

COLS = ["E_readout","E_1q","E_2q","E_2q_log","E_idle","N_SWAP","D"]
WEIGHT_KEYS = ["alpha","beta","gamma","gamma_log","eta_idle","delta","lambda_"]
N_DIM = len(COLS)

# ---------------------------------------------------------------------------
# Spearman
# ---------------------------------------------------------------------------

def spearman_rho(xs: list[float], ys: list[float]) -> tuple[float, float]:
    n = len(xs)
    if n != len(ys):
        raise ValueError("length mismatch")
    def rank(vals):
        sorted_idx = sorted(range(n), key=lambda i: vals[i])
        ranks = [0]*n
        for r,i in enumerate(sorted_idx):
            ranks[i]=r
        return ranks
    rx, ry = rank(xs), rank(ys)
    mx, my = sum(rx)/n, sum(ry)/n
    num = sum((a-mx)*(b-my) for a,b in zip(rx,ry))
    den_x = math.sqrt(sum((a-mx)**2 for a in rx))
    den_y = math.sqrt(sum((b-my)**2 for b in ry))
    if den_x==0 or den_y==0:
        return 0.0, 1.0
    rho = num/(den_x*den_y)
    if abs(rho) >= 1 - 1e-12:
        return rho, 0.0 if n > 2 else 1.0
    t = rho*math.sqrt((n-2)/(1-rho**2)) if abs(rho)<1 else float("inf")
    try:
        from scipy import stats
        p = 2*stats.t.sf(abs(t), n-2)
    except Exception:
        p = 1.0
    return rho, float(p)

# ---------------------------------------------------------------------------
# Data loading & dataset building
# ---------------------------------------------------------------------------

def _load_multi():
    # prefer v2 (now v3 metrics), fallback legacy
    if MULTI_FILE_V2.exists():
        with open(MULTI_FILE_V2) as f:
            j = json.load(f)
        # handle both payload formats: v2 has keys "results"/"meta", legacy has flat?
        return j
    with open(MULTI_FILE_LEGACY) as f:
        return json.load(f)

def load_dataset() -> dict:
    with open(CALIB_FILE) as f:
        calib_j = json.load(f)
    calib_by_q = {r["q"]: r for r in calib_j["qubits"]}
    with open(ROUTER_ANALYSIS_FILE) as f:
        analysis = json.load(f)["cells"]
    multi = _load_multi()
    # single-qubit points: 6 stratified qubits in analysis order
    single_points = []
    for c in analysis:
        q = c["q"]
        row = calib_by_q[q]
        # E_idle for single: depth 2 * (1/T1+1/T2)  — introduces variance even at k=1
        t1 = row.get("T1_us") or 100.0
        t2 = row.get("T2_us") or 100.0
        if t1 <= 0: t1 = 100.0
        if t2 <= 0: t2 = 100.0
        e_idle_single = 2 * (1.0/t1 + 1.0/t2)
        single_points.append({
            "kind": "single",
            "k": 1,
            "q": q,
            "E_readout": float(row["readout_total"]),
            "E_1q": float(row.get("sx_error") or 0),
            "E_2q": 0.0,
            "E_2q_log": 0.0,
            "E_idle": float(e_idle_single),
            "N_SWAP": 0,
            "D": 2,
            "y": float(c["max_dev"]),
            "y_label": "max_dev",
            "layout": [q],
            "T1_us": float(t1),
            "T2_us": float(t2),
        })

    # multi-qubit aggregates k=4/6/8 UniMind
    multi_points = []
    # multi structure: {"results": {"4": {"UniMind": {...}}, ...}} in v2, or legacy same
    results_dict = multi.get("results", multi)
    for k in [4,6,8]:
        ks = str(k)
        if ks not in results_dict:
            continue
        uni = results_dict[ks].get("UniMind", results_dict[ks])
        layout = uni.get("layout") or uni.get("layout_median")
        vals = [calib_by_q[q] for q in layout if q in calib_by_q]
        mean_readout = sum(v["readout_total"] for v in vals)/len(vals) if vals else 0.02
        mean_sx = sum((v.get("sx_error") or 0) for v in vals)/len(vals) if vals else 0.0003
        e2q = float(uni.get("est_2q_error", uni.get("est_2q_additive", 0)))
        # v3 fields: prefer stored, else compute fallback
        if "E_2q_log" in uni:
            e2q_log = float(uni["E_2q_log"])
        elif "E_2q_log_gate" in uni:
            e2q_log = float(uni["E_2q_log_gate"])
        else:
            # fallback: cz_count * -log(1-avg_cz)
            avg_cz = float(uni.get("avg_cz_proxy", 0.005))
            cz_cnt = int(uni.get("cz_count", 0))
            avg_cz = min(max(avg_cz, 1e-6), 0.999)
            e2q_log = cz_cnt * (-math.log(1-avg_cz)) if cz_cnt else 0.0
        if "E_idle" in uni:
            e_idle = float(uni["E_idle"])
        else:
            # fallback: depth * mean(1/T1+1/T2)
            depth = int(uni.get("depth", 0))
            invs = []
            for q in layout:
                r = calib_by_q.get(q)
                if r:
                    t1 = r.get("T1_us") or 100.0
                    t2 = r.get("T2_us") or 100.0
                    if t1<=0: t1=100.0
                    if t2<=0: t2=100.0
                    invs.append(1/t1+1/t2)
            mean_inv = sum(invs)/len(invs) if invs else 0.02
            e_idle = depth * mean_inv
        e_idle = float(e_idle)
        multi_points.append({
            "kind": "multi",
            "k": k,
            "q": None,
            "layout": layout,
            "E_readout": float(mean_readout),
            "E_1q": float(mean_sx),
            "E_2q": float(e2q),
            "E_2q_additive": float(uni.get("est_2q_additive", e2q)),
            "E_2q_log": float(e2q_log),
            "E_2q_log_gate": float(uni.get("E_2q_log_gate", e2q_log)),
            "E_2q_log_layout": float(uni.get("E_2q_log_layout", 0)),
            "E_idle": float(e_idle),
            "mean_inv_T": float(uni.get("mean_inv_T", e_idle / uni.get("depth", 1) if uni.get("depth",0) else 0)),
            "avg_cz_proxy": float(uni.get("avg_cz_proxy", 0)),
            "N_SWAP": int(uni["swap_count"]),
            "D": int(uni["depth"]),
            "cz_count": int(uni.get("cz_count", 0)),
            "y": float(e2q),
            "y_label": "est_2q_error",
        })

    all_points = single_points + multi_points
    return {
        "calib_meta": {"n_qubits": len(calib_by_q), "backend": calib_j.get("backend"), "date": calib_j.get("last_update_date")},
        "multi_meta": multi.get("meta", {}),
        "points": all_points,
    }

def normalize_features(points: list[dict]) -> tuple[np.ndarray, np.ndarray, dict]:
    """Min-max normalize 7 feature columns to [0,1]. Returns X_norm, y, scaling."""
    raw = np.array([[p[c] for c in COLS] for p in points], dtype=float)
    y = np.array([p["y"] for p in points], dtype=float)
    mins = raw.min(axis=0)
    maxs = raw.max(axis=0)
    ranges = maxs - mins
    ranges[ranges==0]=1.0
    X_norm = (raw - mins)/ranges
    scaling = {
        "method": "minmax",
        "columns": COLS,
        "mins": {c: float(m) for c,m in zip(COLS, mins)},
        "maxs": {c: float(m) for c,m in zip(COLS, maxs)},
    }
    return X_norm, y, scaling

def j_scores(X_norm: np.ndarray, w: np.ndarray) -> np.ndarray:
    return X_norm @ w  # w = 7-dim simplex

# ---------------------------------------------------------------------------
# Fitting: Dirichlet simplex sampling
# ---------------------------------------------------------------------------

def fit_simplex(X: np.ndarray, y: np.ndarray, n_samples: int = 8000, seed: int = 42) -> tuple[dict, float, float]:
    """Sample Dirichlet(1,...,1) weights (7-dim), pick max Spearman. Returns params, rho, p."""
    rng = np.random.default_rng(seed)
    best_rho = -2
    best_w = None
    best_p = 1.0
    candidates = []
    # corners
    for i in range(N_DIM):
        w = np.zeros(N_DIM); w[i]=1.0
        candidates.append(w)
    candidates.append(np.full(N_DIM, 1.0/N_DIM))
    # random Dirichlet
    for _ in range(n_samples):
        g = rng.gamma(1,1, size=N_DIM)
        w = g/g.sum()
        candidates.append(w)
    # sparse grid for stability: sample 4 dims varying; simpler random covers remainder
    # add explicit prior center that reflects v2 belief + new dims small
    candidates.append(np.array([0.2,0.35,0.2,0.1,0.05,0.05,0.05]))
    candidates.append(np.array([0.15,0.3,0.15,0.15,0.1,0.05,0.1]))
    for w in candidates:
        s=w.sum()
        if s==0:
            continue
        w = w/s
        J = j_scores(X, w)
        rho, p = spearman_rho(J.tolist(), y.tolist())
        if rho > best_rho:
            best_rho = rho
            best_w = w.copy()
            best_p = p
    params = {k: float(v) for k,v in zip(WEIGHT_KEYS, best_w)}
    return params, float(best_rho), float(best_p)

def params_to_vec(p: dict) -> np.ndarray:
    return np.array([p[k] for k in WEIGHT_KEYS])

# ---------------------------------------------------------------------------
# LOO & Bootstrap
# ---------------------------------------------------------------------------

def run_loo(X: np.ndarray, y: np.ndarray, n_samples: int = 5000) -> dict:
    n = X.shape[0]
    loo_params = []
    train_rhos = []
    y_pred_loo = np.zeros(n)
    for i in range(n):
        mask = np.ones(n, dtype=bool); mask[i]=False
        Xtr, ytr = X[mask], y[mask]
        p, rho, _ = fit_simplex(Xtr, ytr, n_samples=n_samples, seed=42+i*13)
        loo_params.append(p)
        train_rhos.append(rho)
        w = params_to_vec(p)
        y_pred_loo[i] = float(j_scores(X[i:i+1], w)[0])
    loo_rho, loo_p = spearman_rho(y_pred_loo.tolist(), y.tolist())
    weight_stability = {}
    for k in WEIGHT_KEYS:
        vals = np.array([pp[k] for pp in loo_params])
        weight_stability[k] = {
            "mean": float(vals.mean()),
            "std": float(vals.std(ddof=1) if len(vals)>1 else 0.0),
            "min": float(vals.min()),
            "max": float(vals.max()),
            "median": float(np.median(vals)),
            "values": [round(float(v),4) for v in vals],
        }
    folds = []
    for i in range(n):
        folds.append({
            "held_out_idx": i,
            "held_out_kind": "single" if i<6 else "multi",
            "train_rho": round(float(train_rhos[i]),4),
            "params": {k: round(float(loo_params[i][k]),4) for k in WEIGHT_KEYS},
            "y_true": float(y[i]),
            "y_pred_loo": float(y_pred_loo[i]),
        })
    return {
        "folds": folds,
        "loo_rho": round(float(loo_rho),4),
        "loo_p": round(float(loo_p),4),
        "mean_train_rho": round(float(np.mean(train_rhos)),4),
        "std_train_rho": round(float(np.std(train_rhos, ddof=1) if len(train_rhos)>1 else 0),4),
        "weight_stability": weight_stability,
        "y_pred_loo": [round(float(v),6) for v in y_pred_loo],
    }

def run_bootstrap(X: np.ndarray, y: np.ndarray, B: int = 1000, n_samples: int = 3000, seed: int = 123) -> dict:
    n = X.shape[0]
    rng = np.random.default_rng(seed)
    boot_params = []
    rhos = []
    for b in range(B):
        idx = rng.integers(0, n, size=n)
        Xb, yb = X[idx], y[idx]
        p, rho, _ = fit_simplex(Xb, yb, n_samples=n_samples, seed=seed+b*7)
        boot_params.append(p)
        rhos.append(rho)
    weight_stability = {}
    for k in WEIGHT_KEYS:
        vals = np.array([pp[k] for pp in boot_params])
        weight_stability[k] = {
            "mean": float(vals.mean()),
            "std": float(vals.std(ddof=1) if len(vals)>1 else 0.0),
            "min": float(vals.min()),
            "max": float(vals.max()),
            "median": float(np.median(vals)),
            "p5": float(np.percentile(vals,5)),
            "p95": float(np.percentile(vals,95)),
            "p25": float(np.percentile(vals,25)),
            "p75": float(np.percentile(vals,75)),
        }
    rhos_arr = np.array(rhos)
    spearman_dist = {
        "mean": float(rhos_arr.mean()),
        "std": float(rhos_arr.std(ddof=1) if len(rhos_arr)>1 else 0),
        "min": float(rhos_arr.min()),
        "max": float(rhos_arr.max()),
        "median": float(np.median(rhos_arr)),
        "p5": float(np.percentile(rhos_arr,5)),
        "p95": float(np.percentile(rhos_arr,95)),
        "p25": float(np.percentile(rhos_arr,25)),
        "p75": float(np.percentile(rhos_arr,75)),
        "values": [round(float(v),4) for v in rhos_arr[:50]],
        "hist_10bins": np.histogram(rhos_arr, bins=10, range=(0,1))[0].tolist(),
        "hist_bins": np.linspace(0,1,11).round(2).tolist(),
    }
    return {
        "B": B,
        "weight_stability": weight_stability,
        "spearman_dist": spearman_dist,
        "spearman_values_full": [round(float(v),4) for v in rhos_arr],
        "params_samples": [{k: round(float(pp[k]),4) for k in WEIGHT_KEYS} for pp in boot_params[:20]],
    }

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("Loading dataset v3 (single k=1 + multi k=4/6/8 UniMind, 7-dim)...")
    ds = load_dataset()
    points = ds["points"]
    X_norm, y, scaling = normalize_features(points)
    print(f"  n_points={len(points)} (6 single + 3 multi), dims={N_DIM} {COLS}")
    for i,p in enumerate(points):
        print(f"    [{i}] kind={p['kind']} k={p['k']} layout={p['layout'][:4]}{'...' if len(p['layout'])>4 else ''} "
              f"E_r={p['E_readout']:.5f} E1={p['E_1q']:.6f} E2={p['E_2q']:.5f} E2log={p['E_2q_log']:.4f} E_idle={p['E_idle']:.4f} SWAP={p['N_SWAP']} D={p['D']} y={p['y']:.5f}")
    print(f"  scaling mins={scaling['mins']}")
    print(f"  scaling maxs={scaling['maxs']}")

    # Full-data fit
    print("\nFull-data simplex fit (n_samples=8000, 7-dim)...")
    full_params, full_rho, full_p = fit_simplex(X_norm, y, n_samples=8000, seed=42)
    print(f"  full params={full_params} rho={full_rho:.4f} p={full_p:.4f}")

    # LOO
    print("\nLOO-CV (n_samples=5000 per fold, 7-dim)...")
    loo_res = run_loo(X_norm, y, n_samples=5000)
    print(f"  LOO rho={loo_res['loo_rho']} p={loo_res['loo_p']} mean_train_rho={loo_res['mean_train_rho']}")

    # Bootstrap
    print("\nBootstrap B=200 (n_samples=3000 per resample)...")
    boot_res = run_bootstrap(X_norm, y, B=200, n_samples=3000, seed=123)
    print(f"  bootstrap rho mean={boot_res['spearman_dist']['mean']:.4f} std={boot_res['spearman_dist']['std']:.4f}")

    print("\nWeight stability (bootstrap mean±std):")
    for k in WEIGHT_KEYS:
        ws = boot_res["weight_stability"][k]
        print(f"  {k}: {ws['mean']:.3f} ± {ws['std']:.3f}  median {ws['median']:.3f}  [p5 {ws['p5']:.3f} – p95 {ws['p95']:.3f}]")

    # J ranking for full fit
    J_full = j_scores(X_norm, params_to_vec(full_params))
    ranked = sorted(zip(points, J_full, y), key=lambda x: x[1])
    print("\nJ(G) ranking (full fit, 7-dim):")
    for rank,(p,j,yt) in enumerate(ranked,1):
        print(f"  rank {rank}: kind={p['kind']} k={p['k']} J={j:.4f} y={yt:.5f} layout={p['layout']}")

    # Build output
    output = {
        "version": "3.0",
        "J_definition": "J(G) = alpha*E_readout + beta*E_1q + gamma*E_2q + gamma_log*E_2q_log + eta_idle*E_idle + delta*N_SWAP + lambda_*D  (features min-max normalized to [0,1], 7-dim; E_2q_log=Σ -log(1-cz_error) SOTA 2606.12816, E_idle=depth*mean(1/T1+1/T2) SOTA 2405.18785)",
        "U_definition": "U(P) = P_success - lambda1*L - lambda2*C - lambda3*E",
        "dims": N_DIM,
        "columns": COLS,
        "weight_keys": WEIGHT_KEYS,
        "dataset": {
            "n_points": len(points),
            "n_single": 6,
            "n_multi": 3,
            "k_values": [1,4,6,8],
            "points": [
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
                } for i,p in enumerate(points)
            ],
            "scaling": scaling,
            "raw_feature_matrix": [[float(p[c]) for c in COLS] for p in points],
        },
        "full_fit": {
            "params": {k: round(float(v),4) for k,v in full_params.items()},
            "params_raw": full_params,
            "spearman": {"rho": round(float(full_rho),4), "p_value": round(float(full_p),4)},
            "ranking": [
                {"rank": i+1, "idx": int(np.argsort(J_full)[i]), "J": round(float(J_full[np.argsort(J_full)[i]]),6), "y": float(y[np.argsort(J_full)[i]])}
                for i in range(len(points))
            ],
        },
        "loo": loo_res,
        "bootstrap": boot_res,
        "multi_qubit_features": {
            str(p["k"]): {
                "layout": p["layout"],
                "mean_readout": p["E_readout"],
                "mean_sx": p["E_1q"],
                "E_2q": p["E_2q"],
                "E_2q_log": p["E_2q_log"],
                "E_idle": p["E_idle"],
                "N_SWAP": p["N_SWAP"],
                "D": p["D"],
                "y": p["y"],
            } for p in points if p["kind"]=="multi"
        },
        "comparison_v2": {
            "v2_note": "v2: 5-dim (E_readout,E_1q,E_2q,N_SWAP,D), rho=0.85 p=0.0037",
            "v3_features": "7-dim adds E_2q_log (Σ -log(1-p2q)) and E_idle (depth·mean(1/T1+1/T2)) per SOTA P0/P1",
            "v3_validation": "LOO + bootstrap(200) over 7-simplex",
        },
        "method": {
            "fit": "Dirichlet(1) simplex sampling n=8000 (7-dim) + corners/uniform, max Spearman",
            "loo": "leave-one-out, n_samples=5000 per fold, aggregated rho over held-out predictions",
            "bootstrap": "B=200 resample-with-replacement, n_samples=3000 per resample",
            "normalization": "min-max per feature over 9 points before weighting (7 cols)",
            "target_y": "single: max_dev (QPU sweep); multi: est_2q_error (FakeMarrakesh+calib proxy) — ranking target",
            "quota": "zero — all local simulation data",
            "E_2q_log_source": "multi_qubit_routing_v2.json E_2q_log (=cz_count*-log(1-avg_cz)), single=0",
            "E_idle_source": "single: 2*(1/T1+1/T2) per qubit; multi: depth*mean(1/T1+1/T2) from snapshot T1/T2 (calib_full_e08.json)",
        },
        "notes": "v3 extends J(G) to 7 dims with SOTA -log(1-p2q) and idle decoherence proxy, addressing v2 fallback avg_d_err masking by amplifying high-error edge and idle effects; T1/T2 now explicitly read from calibration snapshot.",
    }

    RES.mkdir(parents=True, exist_ok=True)
    ROOT_RES.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)
    with open(OUTPUT_FILE_ROOT, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved -> {OUTPUT_FILE}")
    print(f"Saved -> {OUTPUT_FILE_ROOT}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
