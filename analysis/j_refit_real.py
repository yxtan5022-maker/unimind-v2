"""Refit of the 7-dim J(G) utility model on real refresh-pinned labels.

Replaces the simulator proxy y (= est_2q_error) at k in {9,10,11,12,14,16,18}
with the mean measured max_dev over the two refresh-pinned patterns per k
(data/jgpu/j_real_refresh.json, pins refreshed from the 2026-08-31 snapshot).
Features X are left byte-identical to the v4 dataset so the comparison is a
pure label-side test: how well the fit -- and its size-OOS generalization --
hold when high-k labels come from the real device instead of a proxy.

Outputs analysis/results/utility_model_v5.json (fit + LOO) and
utility_oos_v5.json (size split), plus a v4-vs-v5 delta table.
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RES = ROOT / "analysis" / "results"
sys.path.insert(0, str(ROOT / "analysis"))
from utility_model import COLS, WEIGHT_KEYS, fit_simplex, j_scores, params_to_vec  # noqa: E402

V4 = RES / "utility_model_v4.json"
REAL = DATA / "jgpu" / "j_real_refresh.json"
OUT_M = RES / "utility_model_v5.json"
OUT_OOS = RES / "utility_oos_v5.json"
SEED = 42
MC_PERM = 20000


def main():
    v4 = json.loads(V4.read_text(encoding="utf-8"))
    pts = v4["dataset"]["points"]
    real = json.loads(REAL.read_text(encoding="utf-8"))
    real_by_k = {}
    for r in real["rows"]:
        real_by_k.setdefault(r["k"], []).append(r["max_dev"])
    meas_k = sorted(real_by_k)
    n_real_rows = sum(len(v) for v in real_by_k.values())

    points = []
    for p in pts:
        q = dict(p)
        if p["kind"] == "multi" and p["k"] in real_by_k:
            q["y"] = round(float(np.mean(real_by_k[p["k"]])), 4)
            q["y_label"] = "real_maxdev_mean_refresh0831"
        points.append(q)

    def row(p):
        feats = [p[c] for c in COLS]
        return {"kind": p["kind"], "k": p["k"], "y": p["y"],
                "features": feats, "layout": p.get("layout")}

    data = [row(p) for p in points]

    def fit_and_rank(X, y):
        params, rho, p = fit_simplex(X, y, n_samples=5000, seed=SEED)
        J = j_scores(X, params_to_vec(params))
        from scipy import stats
        sr = stats.spearmanr(J.tolist(), y.tolist())
        return params, float(rho), J, sr

    # ---- full fit on all 23 (7 labels now real) ----
    X = np.array([d["features"] for d in data], dtype=float)
    y = np.array([d["y"] for d in data], dtype=float)
    lo, hi = X.min(axis=0), X.max(axis=0)
    rng = hi - lo
    rng[rng == 0] = 1.0
    Xn = (X - lo) / rng
    params_full, rho_full, J_full, sr_full = fit_and_rank(Xn, y)
    ranking = [{"rank": i + 1, "k": data[ix]["k"], "kind": data[ix]["kind"],
                "J": round(float(J_full[ix]), 4), "y": round(float(data[ix]["y"]), 4)}
               for i, ix in enumerate(sorted(range(len(data)), key=lambda i: -J_full[i]))]

    # ---- LOO (23 folds) ----
    n = len(data)
    loo_pred = np.zeros(n)
    tr_rhos = []
    folds = []
    Xl = np.array([d["features"] for d in data], dtype=float)
    yl = np.array([d["y"] for d in data], dtype=float)
    for i in range(n):
        m = np.ones(n, dtype=bool)
        m[i] = False
        lo_i, hi_i = Xl[m].min(axis=0), Xl[m].max(axis=0)
        rg_i = hi_i - lo_i
        rg_i[rg_i == 0] = 1.0
        Xn_i = (Xl[m].min(axis=0), (Xl[m] - lo_i) / rg_i)
        Xn_tr = Xn_i[1]
        Xn_te = (Xl[i] - lo_i) / rg_i
        prm, rho_tr, _ = fit_simplex(Xn_tr, yl[m], n_samples=4000, seed=SEED)
        J_i = float(j_scores(Xn_te.reshape(1, -1), params_to_vec(prm))[0])
        loo_pred[i] = J_i
        tr_rhos.append(rho_tr)
        folds.append({"held_out_idx": i, "k": data[i]["k"], "kind": data[i]["kind"],
                      "y_true": round(float(yl[i]), 4),
                      "y_pred_loo": round(J_i, 4),
                      "train_rho": round(float(rho_tr), 4)})
    from scipy import stats
    loo_rho, loo_p = stats.spearmanr(loo_pred.tolist(), y.tolist())
    w_loo = list(loo_pred)

    # ---- size-OOS (same protocol as j_utility_oos.py) ----
    train = [d for d in data if d["k"] <= 8]
    test = [d for d in data if d["k"] >= 9]
    X_tr = np.array([d["features"] for d in train], dtype=float)
    X_te = np.array([d["features"] for d in test], dtype=float)
    y_tr = np.array([d["y"] for d in train], dtype=float)
    y_te = np.array([d["y"] for d in test], dtype=float)
    lo_o, hi_o = X_tr.min(axis=0), X_tr.max(axis=0)
    rng_o = hi_o - lo_o
    rng_o[rng_o == 0] = 1.0
    X_tr_n = (X_tr - lo_o) / rng_o
    X_te_n = (X_te - lo_o) / rng_o
    n_oob = int(((X_te_n > 1.0 + 1e-12) | (X_te_n < -1e-12)).any(axis=1).sum())
    X_te_n_c = np.clip(X_te_n, 0, 1)
    params_oos, rho_oos_tr, _ = fit_simplex(X_tr_n, y_tr, n_samples=5000, seed=SEED)
    J_te = j_scores(X_te_n_c, params_to_vec(params_oos))
    rho_oos_te, _ = stats.spearmanr(J_te.tolist(), y_te.tolist())
    rng2 = np.random.default_rng(SEED + 7)
    yp = y_te.copy()
    cnt_ge = 0
    for _ in range(MC_PERM):
        rng2.shuffle(yp)
        r_, _ = stats.spearmanr(J_te.tolist(), yp.tolist())
        if r_ >= rho_oos_te - 1e-12:
            cnt_ge += 1
    p_mc = cnt_ge / MC_PERM

    model = {
        "version": "5.0",
        "note": "v4 feature matrix unchanged; y replaced at k in {} with mean of "
                "{} refresh-pinned measured rows (pass {}/{}); single points unchanged".
                format(meas_k, n_real_rows,
                       sum(1 for r in real["rows"] if r["pass_05"]), len(real["rows"])),
        "dataset": {"n_points": n, "n_single": 6, "n_multi": 17,
                    "n_multi_with_real_label": sum(1 for p in points if p["y_label"].startswith("real"))},
        "full_fit": {"params": {k: round(float(params_full[k]), 4) for k in WEIGHT_KEYS},
                     "spearman": {"rho": round(rho_full, 4),
                                  "p_value": round(float(sr_full.pvalue), 4)},
                     "ranking": ranking},
        "loo": {"loo_rho": round(float(loo_rho), 4),
                "loo_p": round(float(loo_p), 4),
                "mean_train_rho": round(float(np.mean(tr_rhos)), 4),
                "y_pred_loo": [round(x, 4) for x in w_loo],
                "folds": folds},
        "v4_reference": {"full_rho": v4["full_fit"]["spearman"]["rho"],
                         "loo_rho": v4["loo"]["loo_rho"]},
        "delta": {"d_full_rho": round(rho_full - v4["full_fit"]["spearman"]["rho"], 4),
                  "d_loo_rho": round(float(loo_rho) - v4["loo"]["loo_rho"], 4),
                  "d_oos_te_rho": round(float(rho_oos_te) - 0.8181, 4)},
        "real_labels": {"k_values": meas_k, "per_k_mean": {k: round(float(np.mean(v)), 4)
                                                           for k, v in real_by_k.items()}},
    }
    oos = {
        "method": "size-out-of-sample, same protocol as utility_oos.json but labels "
                  "at k>=9 replaced by refresh-pinned real max_dev",
        "n_train_k8": len(train), "n_test_k9": len(test),
        "train": {"spearman": round(float(rho_oos_tr), 4),
                  "weights": {k: round(float(params_oos[k]), 4) for k in WEIGHT_KEYS}},
        "test": {"spearman": round(float(rho_oos_te), 4),
                 "spearman_p_mc_%d" % MC_PERM: round(p_mc, 4),
                 "n_oob_before_clip": int(n_oob)},
        "v4_oos_reference": {"train_rho": 0.8848, "test_rho": 0.8181,
                             "mc_p": 0.0029, "test_k": "9..18"},
    }
    OUT_M.write_text(json.dumps(model, indent=1, ensure_ascii=False))
    OUT_OOS.write_text(json.dumps(oos, indent=1, ensure_ascii=False))

    print("== v5 refit on real labels (k=%s -> real max_dev) ==" % meas_k)
    print("full rho = {:.4f}  (v4 {:.4f};  delta {:+.4f})".format(
        rho_full, v4["full_fit"]["spearman"]["rho"], model["delta"]["d_full_rho"]))
    print("LOO  rho = {:.4f}  (v4 {:.4f};  delta {:+.4f})".format(
        float(loo_rho), v4["loo"]["loo_rho"], model["delta"]["d_loo_rho"]))
    print("OOS  rho = {:.4f}  MC p={:.4f}  (v4 {:.4f})".format(
        float(rho_oos_te), p_mc, 0.8181))
    print("weights full v5: " + ", ".join("%s=%.3f" % (k, params_full[k]) for k in WEIGHT_KEYS))
    print("real labels y (mean max_dev):", {k: model["real_labels"]["per_k_mean"][k] for k in meas_k})
    print("written ->", OUT_M, "and", OUT_OOS)


if __name__ == "__main__":
    main()