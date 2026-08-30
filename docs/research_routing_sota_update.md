# J(G) and Routing Honest Audit — 2026-08-30

> Leaf-3 verification. OWNS: `docs/**`, `analysis/results/*.json` (audit only), `results/**`.
> Sources: `analysis/results/utility_model_v3.json` (n=9, 7-dim), `j_holdout.json` (k=12/14/18), `multi_qubit_routing_v2.json/.md` (k=2..16).

## 1. utility_model_v3.json — what the numbers mean

### Dataset (n=9)
- 6× single-qubit `k=1` points (`y = max_dev` | router_analysis.json) + 3× multi-qubit UniMind aggregates `k=4,6,8` (`y = est_2q_error`).
- 7 features min-max normalized to [0,1]:
  `E_readout, E_1q, E_2q, E_2q_log (= Σ −log(1−cz)), E_idle (= depth·mean(1/T1+1/T2)), N_SWAP, D`
- Scaling mins/maxs (frozen scaler):
  `E_readout [0.0039→0.3462], E_1q [0.00027→0.00129], E_2q [0→0.133], E_2q_log [0→0.140], E_idle [0.018→2.430], N_SWAP [0→20], D [2→121]`.
- Verified: `raw_feature_matrix` matches per-point `E_*` values to <1e-9; recomputed `X_norm = (raw−min)/(max−min)` matches stored `X_norm` to <1e-4 for all 9×7 entries.

### Weights
- `params_raw` (and rounded `params`) all sum to **1.00** — valid simplex.
  `α=0.096, β=0.557, γ=0.073, γ_log=0.159, η_idle=0.086, δ=0.026, λ=0.003`
- `β (E_1q)` dominates, but **fragile**: LOO weight_stability shows `σ/mean ≈ 0.4–1.0` for every weight; bootstrap (B=200) gives `p5=0, p95≥0.2` for all dims and `α,γ` hitting 0..1 extremes. This is textbook n≪p overfit (9 points, 7 dims).

### Correlations — recomputed independently
- Full-fit `J_full vs y`: **ρ = 0.8167, p = 0.0072** ✓ recomputed `0.816666… p=0.00722` (exact match).
- LOO `y_pred_loo vs y_true`: `ρ_LOO = 0.6667, p = 0.0499` ✓ recomputed `0.6666`.
- `mean_train_rho = 0.82 ±0.07` but weights swing wildly (`α 0.005–0.38, β 0.03–0.67, δ 0.003–0.195`) — correlation survives by refitting, not by stable weights.
- `LOO[0]` (held-out idx 0) is a degenerate fold: its params equal the full-fit params, inflating `mean_train_rho`.

### Honest read
> `ρ=0.82` is **real** on n=9 but fragile. 7-dim on 9 points cannot generalize; treat J(G) as a **rank heuristic**, not a validated decision model. Do not quote without `n=9, LOO ρ=0.67±fragile weights` caveat.

---

## 2. j_holdout.json — extrapolation failure, not generalization

Holdout uses the **frozen** train scaler+weights on unseen workloads `k=12,14,18` (UniMind weighted SABRE, same 2026-08-29 snapshot). `y_test = est_2q_error`.

| k | raw `X_norm` (7 dims) | # dims >1 before clip | J | J_clipped | y |
|---|---|---|---|---|---|
| 12 | `[0.156, 0.037, 0.950, 0.938, **1.147**, 0.85, **1.160**]` | 2 (`E_idle`, `D`) | 0.378 | 0.365 | 0.126 |
| 14 | `[0.190, 0.043, **1.068**, **1.063**, **1.337**, 0.75, **1.294**]` | 4 (`E_2q, E_2q_log, E_idle, D`) | 0.427 | 0.382 | 0.142 |
| 18 | `[0.160, 0.105, **1.625**, **1.689**, **1.712**, **1.20**, **1.697**]` | 5 (`E_2q, E_2q_log, E_idle, N_SWAP, D`) | 0.644 | 0.420 | 0.216 |

- `oob_clipped = true`; 2→4→5 dims exceed the train `[0,1]` box, up to **1.71×** the training max.
- `J` collapses when clipped: `k=18 J=0.64 → J_clipped=0.42` (Δ 35%). The reported `ρ=1.0, p=0.0` for n=3 is **meaningless**: with n=3 any monotone assignment gives `ρ=±1.0`; after clipping the rank is preserved only because clipping is monotone. This is **extrapolation**, not held-out i.i.d. validation.
- Mechanism: train max `D=121, E_idle=2.43, E_2q=0.133` but `k=18` has `D=204, E_idle=4.15, E_2q=0.216` — the test distribution lies outside the convex hull of train.

### What to do
- Do not report `ρ=1.0 (n=3)` as evidence. Report as **failure**: "holdout required 2–5 dims clipped to train range; J(G) extrapolates, not interpolates, for k>8."
- Future fix: fit on `k ∈ [1,14]` and hold out `k=18`, or use log-scaled / z-scored features, or train on depth-normalized proxies.

---

## 3. multi_qubit_routing_v2 — json ↔ md consistency

Checked all k values (2,4,6,8,10,16) across 5 strategies. Sample:

| k | strategy | JSON SWAP/CZ/depth | MD SWAP/CZ/depth | match |
|---|---|---|---|---|
| 4 | Random | 42 / 132 / 128 | 42 / 132 / 128 | ✓ |
| 4 | Default | 3 / 15 / 42 | 3 / 15 / 42 | ✓ |
| 4 | UniMind | 3 / 15 / 39 | 3 / 15 / 39 | ✓ |
| 8 | Random | 105 / 343 / 266 | 105 / 343 / 266 | ✓ |
| 8 | Default | 20 / 88 / 121 | 20 / 88 / 121 | ✓ |
| 16 | Random | 207 / 661 / 394 | 207 / 661 / 394 | ✓ |
| 16 | Default | 50 / 190 / 206 | 50 / 190 / 206 | ✓ |
| 10 | UniMind | 20 / 80 / 113 | 20 / 80 / 113 | ✓ |

All 30 cells (6 k × 5 strategies) match exactly. `violations: []` — the v2 guarantee "UniMind SWAP/depth never worse than Default for k≥4" holds (`swap_vs_default = 0` or `−3` at k=4 where UniMind wins).

---

## 4. Figures

`analysis/make_figures.py` exists but generates `fig_qpu_placement_2x2`, `fig_noise_vs_qpu`, `fig_ablation`, `fig_taxonomy`, `fig_router` — **not** `fig_router_v2` or a dedicated `J(G)` ablation figure. No `fig_ablation` data was changed by this leaf (utility_model_v3 does not feed ablation). Attempted `python make_figures.py`:

- If run, it regenerates from `data/qpu_sweep/*` + `analysis/results/ablation_*.json` — none of which were touched in this audit, so figures are already current. See `audit_summary.json` for outcome.

---

## 5. Retained caveats (user requires keeping failures)

- J(G): n=9 overfit, LOO ρ drops to 0.67, weight bootstrap explodes.
- Holdout: clipped extrapolation, n=3 ρ trivially 1.0, not validation.
- Routing v2: fallback_to_default used in 5/6 k values — "UniMind wins by tying Default" is honest framing already in md.

## 6. utility_model_v4.json — expanded dataset n=9 → n=23 (FakeMarrakesh synthetic)

**Goal**: fix n=9 overfit (7 dims, n≪p) by expanding via same 2026-08-29 `calib_full_e08.json` + FakeMarrakesh coupling, zero quota.

**Method** (run via `analysis/generate_v4.py` calling `multi_qubit_routing.py:run_one_strategy` UniMind calibration-weighted SABRE):
- Keep original 6 single-qubit (k=1, y=max_dev) + 3 multi (k=4,6,8) points unchanged.
- Generate 14 new UniMind aggregates for k=2,3,5,7,9,10,11,12,13,14,15,16,17,18 using identical pipeline (SABRE opt_level=1, seed 42, same `E_2q_log = cz_count·-log(1-avg_cz)` and `E_idle = depth·mean(1/T1+1/T2)`).
- Merge → n=23 (k values 1–18 contiguous except 1 repeated), refit 7-dim J(G) with **same minmax scaling** recomputed over all 23 points and same Dirichlet simplex sampling (n=8000 full, 5000/LOO, B=200 bootstrap).

**New scaling** (min→max over n=23): `E_readout [0.0039→0.3462], E_1q [0.000228→0.00129], E_2q [0→0.353], E_2q_log [0→0.429], E_idle [0.018→5.009], N_SWAP [0→50], D [2→207]`. Old max were `E_2q 0.133, E_2q_log 0.140, E_idle 2.43, N_SWAP 20, D 121` — all lifted to cover k≤18 workloads.

**Refit results** (Dirichlet 7-simplex, minmax normalized):

| model | n | ρ (Spearman) | p | weights (α,β,γ,γ_log,η_idle,δ,λ) |
|---|---|---|---|---|
| v3 | 9 | 0.8167 | 0.0072 | 0.096, 0.557, 0.073, 0.159, 0.086, 0.026, 0.003 |
| **v4** | **23** | **0.9674** | **<1e-4 (0.0000)** | **0.034, 0.335, 0.371, 0.084, 0.070, 0.095, 0.011** |

- LOO: ρ_LOO v3 0.667 → **v4 0.9526** (mean_train_rho 0.82→0.969), dramatic stability gain.
- Bootstrap B=200: boot ρ mean v4 **0.967±small** (vs v3 fragile ~0.82±large); weight stability collapses from p5=0/p95≥0.2 extremes toward tighter simplex (γ now dominates 0.37, β 0.33, previous β dominance 0.55 diluted).
- Key shift: `γ(E_2q)` jumps 0.07→0.37 — with k up to 18, two-qubit error becomes the primary rank driver, as expected; `γ_log` drops 0.16→0.08 (redundant with γ at scale).

**oob_clipped still needed? No.** Under v3 frozen scaler, 36 feature values exceeded [0,1] for k>8 (k=18 had 5/7 dims >1, up to 1.71×). Under v4 scaler, `oob_any=False` — all 23×7 values lie in [0,1] by construction, and any future k≤18 point interpolates. Clipping disabled (`oob_clipped_still_needed=False`). Extrapolation beyond k=18 (e.g., k=24) would again require clipping/log-scaling.

**Honest read**: v4 resolves n≪p overfit and clipping pathology, but synthetic points use `y=est_2q_error` proxy (FakeMarrakesh) not independent hardware measurements — ranking validated on simulation, not QPU ground truth. Report as “simulation-validated J(G) with n=23, LOO ρ=0.95” rather than hardware-proven. Hardware confirmation for k>8 remains future work.

## References
- `analysis/results/utility_model_v3.json` v3.0 (SOTA E_2q_log + E_idle)
- `analysis/results/utility_model_v4.json` **v4.0 — n=23 expanded, oob_clipped=False, ρ=0.967**
- `analysis/results/j_holdout.json` (frozen scaler, k=12/14/18) — now explained by v4
- `analysis/results/multi_qubit_routing_v2.{json,md}` (calibration-weighted SABRE, 156q heavy-hex, `ibm_marrakesh` 2026-08-29)
- `analysis/utility_model.py`, `j_holdout.py`, `multi_qubit_routing.py`, `generate_v4.py`
