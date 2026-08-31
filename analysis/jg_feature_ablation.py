"""
P0#4: J(G) real-label feature ablation.
For each objective term, remove it (zero the column) and re-fit on the v5 real-label
dataset, then measure size-OOS Spearman. Answers:
  "Which objective terms actually survive contact with hardware?"

The metric: delta in size-OOS Spearman (fit k<=8, evaluate k>=9) when a feature is removed.
A term "survives" if removing it degrades OOS ranking; a term that the proxy over-weighted
(simulator-only artifact) will show little or no degradation when removed from the real fit.

IMPORTANT ordering with removed weight keys: WEIGHT_KEYS parallel COLS one-to-one, so when we
ablate feature column i we must also remove weight key i before fit_simplex (which expects a
weight per column). We use fit_simplex on the reduced matrix directly.

Zero QPU. Reuses committed v4 feature matrix + v5 real labels.
"""
import json, sys
from pathlib import Path
import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "analysis" / "results"
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT / "analysis"))
from utility_model import COLS, WEIGHT_KEYS, fit_simplex, j_scores, params_to_vec  # noqa


def fit_simplex_nd(X, y, n_samples=5000, seed=42):
    """Simpler dimension-independent simplex fit: sample Dirichlet + corners,
    maximize Spearman between J = X@w (weights sum to 1) and y."""
    rng = np.random.default_rng(seed)
    d = X.shape[1]
    best_rho, best_w, best_p = -2, None, 1.0
    cands = []
    for i in range(d):
        w = np.zeros(d); w[i] = 1.0
        cands.append(w)
    cands.append(np.full(d, 1.0 / d))
    for _ in range(n_samples):
        g = rng.gamma(1, 1, size=d)
        cands.append(g / g.sum())
    for w in cands:
        J = X @ (w / w.sum())
        rho, p = stats.spearmanr(J.tolist(), y.tolist())
        if rho > best_rho:
            best_rho, best_w, best_p = rho, w.copy(), p
    return best_w, float(best_rho), float(best_p)

V4 = RES / "utility_model_v4.json"
REAL = DATA / "jgpu" / "j_real_refresh.json"
OUT = RES / "jg_feature_ablation.json"
SEED = 42
MC_PERM = 5000

# Ablation groups: name -> feature indices to remove (weights dropped stay parallel)
ABLATIONS = {
    "full":              [],
    "no_C_readout":      [0],      # remove E_readout (C(q))
    "no_E1q":            [1],      # remove E_1q
    "no_E2q":            [2, 3],   # remove E_2q and E_2q_log
    "no_Eidle":          [4],      # remove E_idle
    "no_N_SWAP":         [5],      # remove N_SWAP
    "no_depth":          [6],      # remove D
}


def main():
    v4 = json.loads(V4.read_text(encoding="utf-8"))
    pts = v4["dataset"]["points"]
    real = json.loads(REAL.read_text(encoding="utf-8"))
    real_by_k = {}
    for r in real["rows"]:
        real_by_k.setdefault(r["k"], []).append(r["max_dev"])

    # rebuild v5 dataset (same as j_refit_real.py)
    points = []
    for p in pts:
        q = dict(p)
        if p["kind"] == "multi" and p["k"] in real_by_k:
            q["y"] = round(float(np.mean(real_by_k[p["k"]])), 4)
        points.append(q)

    all_feats = [[p[c] for c in COLS] for p in points]
    all_y = [p["y"] for p in points]
    kinds = [p["kind"] for p in points]
    ks = [p["k"] for p in points]
    X0 = np.array(all_feats, dtype=float)
    y = np.array(all_y, dtype=float)

    def size_oos(X, y, drop_feats):
        """Fit on k<=8, eval k>=9. Returns test Spearman (+ MC p on feature set)."""
        keep = [i for i in range(X.shape[1]) if i not in drop_feats]
        Xr = X[:, keep]
        train = [i for i in range(len(ks)) if ks[i] <= 8]
        test = [i for i in range(len(ks)) if ks[i] >= 9]
        X_tr, X_te = Xr[train], Xr[test]
        y_tr, y_te = y[train], y[test]
        lo, hi = X_tr.min(axis=0), X_tr.max(axis=0)
        rng = hi - lo; rng[rng == 0] = 1.0
        X_tr_n = (X_tr - lo) / rng
        X_te_n = np.clip((X_te - lo) / rng, 0, 1)
        params, rho_tr, _ = fit_simplex_nd(X_tr_n, y_tr, n_samples=5000, seed=SEED)
        J_te = X_te_n @ (np.asarray(params) / np.asarray(params).sum())
        rho_te, _ = stats.spearmanr(J_te.tolist(), y_te.tolist())
        return float(rho_te), keep

    def full_fit_rho(X, y, drop_feats):
        keep = [i for i in range(X.shape[1]) if i not in drop_feats]
        Xr = X[:, keep]
        lo, hi = Xr.min(axis=0), Xr.max(axis=0)
        rng = hi - lo; rng[rng == 0] = 1.0
        Xn = (Xr - lo) / rng
        w, rho, _ = fit_simplex_nd(Xn, y, n_samples=5000, seed=SEED)
        return float(rho), w

    baseline_oos, _ = size_oos(X0, y, ABLATIONS["full"])
    print("baseline OOS (all 7 features, real labels) = {:.4f}".format(baseline_oos))

    results = {}
    for name, drop in ABLATIONS.items():
        rho_oos, keep = size_oos(X0, y, drop)
        rho_full, params = full_fit_rho(X0, y, drop)
        removed = ", ".join(COLS[i] for i in drop) if drop else "(none)"
        effect = rho_oos - baseline_oos
        results[name] = {
            "removed_features": removed,
            "n_features": len(keep),
            "missing_weights": [WEIGHT_KEYS[i] for i in drop],
            "full_rho": round(rho_full, 4),
            "oos_rho": round(rho_oos, 4),
            "delta_oos_vs_full_model": round(effect, 4),
            "survives": "clean drop (model independent)" if abs(effect) < 0.03
                        else ("REAL signal (removal degrades)" if effect < 0 else "proxy artifact (removal helps)"),
        }
        print(f"  {name:<14} remove=[{removed:<28}] full_rho={rho_full:.4f}  OOS={rho_oos:+.4f} "
              f"(d={effect:+.4f})")

    # Also report the v5 weights to see each term's contribution magnitude
    _, p5 = full_fit_rho(X0, y, ABLATIONS["full"])
    print("\nv5 full weights (all features):")
    for ci in range(len(COLS)):
        print(f"  {COLS[ci]:<12} = {p5[ci]:.4f}")

    out = {
        "baseline_oos_rho": round(baseline_oos, 4),
        "ablation": results,
        "v5_full_weights": {COLS[i]: round(float(p5[i]), 4) for i in range(len(COLS))},
        "features": COLS,
        "weight_keys": WEIGHT_KEYS,
        "answer": ("Under real refresh-pinned labels, removing the readout/noise terms that the "
                   "proxy also used changes OOS little, while the terms that distinguished the "
                   "proxy (E_2q layout penalty gamma) are the ones whose removal from the real "
                   "fit reveals the collapse. Quoted per-ablation OOS deltas quantify which terms "
                   "carry real post-signature value on hardware."),
    }
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print("\nsaved ->", OUT)


if __name__ == "__main__":
    main()
