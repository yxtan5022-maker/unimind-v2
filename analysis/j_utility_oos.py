"""Out-of-sample validation of the 7-dim J(G) utility model.

Held-out-split OUT-OF-SAMPLE protocol: fit the 7 simplex weights on the
k <= 8 points and evaluate on k >= 9 points that did NOT participate in
fitting in any way (features rescaled with train-only min/max). This tests
size generalization (whether J(G) predicts circuits larger than any it was
trained on) -- the decision-model test.

Labels: single-qubit y = max_dev (real QPU); multi-qubit y = est_2q_error
(simulator proxy). Outputs analysis/results/utility_oos.json.
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "analysis" / "results"
sys.path.insert(0, str(ROOT / "analysis"))
from utility_model import COLS, WEIGHT_KEYS, fit_simplex, j_scores, params_to_vec  # noqa: E402

V4 = RES / "utility_model_v4.json"
OUT = RES / "utility_oos.json"
MC_PERM = 20000
SEED = 42


def main():
    v4 = json.loads(V4.read_text(encoding="utf-8"))
    pts = v4["dataset"]["points"]
    n_tot = len(pts)

    def row(p):
        feats = [p[c] for c in COLS]
        return {"kind": p["kind"], "k": p["k"], "y": p["y"],
                "features": feats, "q": p.get("q"), "layout": p.get("layout")}

    data = [row(p) for p in pts]

    train = [d for d in data if d["k"] <= 8]
    test = [d for d in data if d["k"] >= 9]
    n_tr, n_te = len(train), len(test)

    X_tr = np.array([d["features"] for d in train], dtype=float)
    X_te = np.array([d["features"] for d in test], dtype=float)
    y_tr = np.array([d["y"] for d in train], dtype=float)
    y_te = np.array([d["y"] for d in test], dtype=float)

    # train-only min-max scaling
    lo = X_tr.min(axis=0)
    hi = X_tr.max(axis=0)
    rng = hi - lo
    rng[rng == 0] = 1.0
    X_tr_n = (X_tr - lo) / rng
    X_te_n = (X_te - lo) / rng
    # clip test features (fresh k > 8 naturally exceeds train range)
    n_oob_test = int(((X_te_n > 1.0 + 1e-12) | (X_te_n < -1e-12)).any(axis=1).sum())
    X_te_n_c = np.clip(X_te_n, 0, 1)

    params, rho_tr, p_tr = fit_simplex(X_tr_n, y_tr, n_samples=5000, seed=SEED)

    J_te = j_scores(X_te_n_c, params_to_vec(params))
    from scipy import stats
    sr = stats.spearmanr(J_te.tolist(), y_te.tolist())
    rho_te = float(sr.correlation)

    rng2 = np.random.default_rng(SEED + 7)
    n_perm = 0
    n_perm_ge = 0
    yp_te = y_te.copy()
    for _ in range(MC_PERM):
        rng2.shuffle(yp_te)
        r_, _ = stats.spearmanr(J_te.tolist(), yp_te.tolist())
        n_perm += 1
        if r_ >= rho_te - 1e-12:
            n_perm_ge += 1
    p_mc = n_perm_ge / n_perm

    # weight stability vs the all-data v4 fit
    w_oos = params_to_vec(params)
    w_v4 = params_to_vec(v4["full_fit"]["params"])
    w_l1 = float(np.abs(w_oos - w_v4).sum())

    res = {
        "method": "size-out-of-sample: fit on k<=8 points, report on k>=9 points; "
                  "features scaled with train-only min/max; weights via fit_simplex "
                  "(max-Spearman, Dirichlet+corners, n=5000, seed=42); test clip at [0,1] "
                  "with out-of-range counted",
        "n_total": n_tot, "n_train_k8": n_tr, "n_test_k9": n_te,
        "n_test_feature_oob_before_clip": int(n_oob_test),
        "train": {"k_range": "1..8", "spearman": round(rho_tr, 4),
                  "spearman_p": round(p_tr, 4),
                  "weights": {k: round(float(params[k]), 4) for k in WEIGHT_KEYS}},
        "test": {"k_range": "9..18", "n": n_te,
                 "spearman": round(rho_te, 4),
                 "spearman_p_t": round(float(sr.pvalue), 4),
                 "spearman_p_mc_%d" % MC_PERM: round(p_mc, 4),
                 "k_vals": sorted({d["k"] for d in test}),
                 "n_single": sum(1 for d in test if d["kind"] == "single"),
                 "n_multi": sum(1 for d in test if d["kind"] == "multi")},
        "v4_all_data": {"full_rho": v4["full_fit"]["spearman"]["rho"],
                        "loo_rho": v4["loo"]["loo_rho"],
                        "weights": {k: round(float(v4["full_fit"]["params"][k]), 4)
                                    for k in WEIGHT_KEYS}},
        "weight_l1_v4_vs_oos": round(w_l1, 4),
    }
    with OUT.open("w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, ensure_ascii=False)

    print("== J(G) size-OOS (train k<=8, n=%d | test k>=9, n=%d) ==" % (n_tr, n_te))
    print("train rho=%.4f (p=%.4f)" % (rho_tr, p_tr))
    print("test  rho=%.4f  (t-approx p=%.3f, MC p=%.4f)  oob-before-clip=%d" %
          (rho_te, sr.pvalue, p_mc, n_oob_test))
    print("test k values:", sorted({d["k"] for d in test}))
    print("weights OOS:  " + ", ".join("%s=%.3f" % (k, params[k]) for k in WEIGHT_KEYS))
    print("weights v4 :  " + ", ".join("%s=%.3f" % (k, v4["full_fit"]["params"][k]) for k in WEIGHT_KEYS))
    print("L1 |w_oos - w_v4| = %.3f" % w_l1)
    print("written ->", OUT)


if __name__ == "__main__":
    main()