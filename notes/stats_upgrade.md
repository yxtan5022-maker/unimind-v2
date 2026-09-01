# Statistical upgrade: refresh-pinned 6-qubit angle suite (n=30/arm)

_All numbers script-computed by `analysis/stats_upgrade.py` on the repo's
per-trial D0-D2 hardware data (`data/e2e/e2e_angle_{full,ablated}_refresh.json`,_frozen for contrast)._

## Data (per-trial, repo ground truth)

| Arm | n | passes | proportion |
|---|---|---|---|
| FULL (calibration-pinned) | 30 | 21 | 70.0% |
| ABLATED (free placement)  | 30 | 23 | 76.7% |

Contrast: frozen (D0) pins run gave FULL 11/30 (36.7%), ABLATED 12/30 (40.0%).

## Wilson 95% intervals

- FULL:  **70.0%**  CI [52.1, 83.3]
- ABLATED: **76.7%** CI [59.1, 88.2]
- Overlap is substantial: the intervals overlap from 59.1% to 83.3%.

## Two-proportion z test (H0: p_FULL = p_ABLATED)

- pooled SE:   z = -0.584, p = 0.559
- unpooled SE: z = -0.586, p = 0.558
- Observed difference (FULL - ABLATED): -6.7 pp — **not statistically distinguishable** at 5% (p>>0.05).

## Minimum detectable effect at n=30/arm (power=0.8, alpha=0.05)

- Around ABLATED rate 76.7%: detect |delta| ≥ 22.9 pp with power 0.8.
- Around FULL rate 70.0%: detect |delta| ≥ 26.5 pp with power 0.8.
- A 6.7 pp difference is **far below** the detection floor: the study cannot distinguish a 6.7 pp gap from zero at 80% power.

## TOST equivalence (delta=15pp)

- One-sided H0 tests at level 0.05 (90% CI on difference).
- 90% CI on (FULL−ABLATED): [-25.40, +12.06]
- Lower equivalence bound −15 pp within CI? False  (CI low -25.4 ≥ −15?)
- Upper equivalence bound +15 pp within CI? True  (CI high +12.1 ≤ +15?)
- **Equivalence at delta=15pp concluded? False**

Interpretation: at delta=15pp we **cannot** conclude equivalence; the 90% CI on the difference spans -25.4 to +12.1, wider than the ±15 pp window. We can only claim **indistinguishability under this sample** (no significant difference detected, small power), never equivalence.

## Honest bottom line (for the paper)

With n=30/arm the measured −6.7 pp (FULL below ABLATED) is within noise (p=0.56 two-proportion). Wilson intervals overlap; the detection floor is [>~26 pp], so this study cannot separate a 6.7 pp gap from zero. TOST at delta=15pp is NOT met, so we claim indistinguishability under our sample, not equivalence.
