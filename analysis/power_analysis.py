"""Phase 7: Power analysis on existing E2E angle data.
Compute effect sizes, confidence intervals, and post-hoc power.
No new QPU runs needed."""
import json
from pathlib import Path
import numpy as np
from scipy import stats
from scipy.stats import norm

def wilson_ci(p, n, alpha=0.05):
    """Wilson score interval for a single proportion."""
    z = norm.ppf(1 - alpha / 2)
    phat = p / n
    denom = 1 + z**2 / n
    center = (phat + z**2 / (2 * n)) / denom
    half = z * np.sqrt(phat * (1 - phat) / n + z**2 / (4 * n**2)) / denom
    return center - half, center + half

def wilson_ci_manual(p_pass, n):
    return wilson_ci(p_pass, n)

ROOT = Path(r"C:\Users\SCSM11\Desktop\unimind-v2")
E2E = ROOT / "data" / "e2e"
OUT = ROOT / "analysis" / "results"

# Load angle E2E data
def load_angle_pass(path):
    with open(path) as f:
        data = json.load(f)
    hw = data.get("hardware", [])
    pass_count = sum(1 for h in hw if h.get("hw_pass", False))
    total = len(hw)
    return pass_count, total, hw

frozen_full_pass, frozen_full_n, _ = load_angle_pass(E2E / "e2e_angle_full.json")
frozen_abl_pass, frozen_abl_n, _ = load_angle_pass(E2E / "e2e_angle_ablated.json")
refresh_full_pass, refresh_full_n, _ = load_angle_pass(E2E / "e2e_angle_full_refresh.json")
refresh_abl_pass, refresh_abl_n, _ = load_angle_pass(E2E / "e2e_angle_ablated_refresh.json")

print("=== E2E Angle Pass Rates ===")
arms = {
    "frozen_full": (frozen_full_pass, frozen_full_n),
    "frozen_ablated": (frozen_abl_pass, frozen_abl_n),
    "refresh_full": (refresh_full_pass, refresh_full_n),
    "refresh_ablated": (refresh_abl_pass, refresh_abl_n),
}
for name, (p, n) in arms.items():
    rate = p / n
    ci_low, ci_high = wilson_ci_manual(p, n)
    print(f"  {name}: {p}/{n} = {rate:.1%} (CI {ci_low:.1%}-{ci_high:.1%})")

# Wilson CI for differences
def wilson_diff_ci(p1, n1, p2, n2, alpha=0.05):
    """CI for difference in proportions (Wilson)."""
    from scipy.stats import norm
    z = norm.ppf(1 - alpha / 2)
    p1_hat, p2_hat = p1 / n1, p2 / n2
    diff = p1_hat - p2_hat
    se = np.sqrt(p1_hat * (1 - p1_hat) / n1 + p2_hat * (1 - p2_hat) / n2)
    return diff, diff - z * se, diff + z * se

print("\n=== Pairwise Comparisons (Wilson CI) ===")
pairs = [
    ("frozen_full", "refresh_full", "Refresh effect (full arm)"),
    ("frozen_ablated", "refresh_ablated", "Refresh effect (ablated arm)"),
    ("refresh_full", "refresh_ablated", "Pinned vs free (refresh)"),
    ("frozen_full", "frozen_ablated", "Pinned vs free (frozen)"),
]
for a, b, label in pairs:
    p1, n1 = arms[a]
    p2, n2 = arms[b]
    diff, lo, hi = wilson_diff_ci(p1, n1, p2, n2)
    # Fisher's exact test
    table = [[p1, n1 - p1], [p2, n2 - p2]]
    _, p_fisher = stats.fisher_exact(table)
    sig = "*" if p_fisher < 0.05 else "n.s."
    print(f"  {label}: delta={diff:+.1%} [{lo:+.1%}, {hi:+.1%}] p={p_fisher:.4f} {sig}")

# Post-hoc power for the pinned-vs-free comparison (refresh arm)
print("\n=== Post-hoc Power Analysis ===")
# Effect: refresh_full=21/30 vs refresh_ablated=23/30
# H0: no difference; observed effect ~ -6.7pp
p1, n1 = refresh_full_pass, refresh_full_n
p2, n2 = refresh_abl_pass, refresh_abl_n
observed_diff = abs(p1/n1 - p2/n2)

# Sensitivity: minimum detectable effect at 80% power, alpha=0.05, n=30 per arm
from scipy.stats import norm
z_alpha = norm.ppf(0.975)  # two-sided
z_beta = norm.ppf(0.80)
pooled_p = (p1 + p2) / (n1 + n2)
se_pooled = np.sqrt(pooled_p * (1 - pooled_p) * (1/n1 + 1/n2))
min_detectable = (z_alpha + z_beta) * se_pooled

print(f"  Observed |delta|: {observed_diff:.1%}")
print(f"  Pooled p: {pooled_p:.3f}")
print(f"  Min detectable effect (80% power, n={n1}/arm): {min_detectable:.1%}")
print(f"  Our effect is {'DETECTABLE' if observed_diff >= min_detectable else 'NOT DETECTABLE'} at 80% power")

# Also compute for frozen arm comparison
p1f, n1f = frozen_full_pass, frozen_full_n
p2f, n2f = frozen_abl_pass, frozen_abl_n
observed_diff_frozen = abs(p1f/n1f - p2f/n2f)
pooled_p_frozen = (p1f + p2f) / (n1f + n2f)
se_pooled_frozen = np.sqrt(pooled_p_frozen * (1 - pooled_p_frozen) * (1/n1f + 1/n2f))
min_detectable_frozen = (z_alpha + z_beta) * se_pooled_frozen
print(f"\n  Frozen arm: observed |delta|={observed_diff_frozen:.1%}, min detectable={min_detectable_frozen:.1%}")
print(f"  Frozen comparison is {'DETECTABLE' if observed_diff_frozen >= min_detectable_frozen else 'NOT DETECTABLE'} at 80% power")

# Chi-squared test for overall 2x2 table
print("\n=== Chi-squared: Refresh vs Frozen ===")
# 2x2: rows=[frozen, refresh], cols=[full_pass, full_fail]
table_refresh = [[frozen_full_pass, frozen_full_n - frozen_full_pass],
                  [refresh_full_pass, refresh_full_n - refresh_full_pass]]
chi2, p_chi2, dof, expected = stats.chi2_contingency(table_refresh)
print(f"  Full arm: chi2={chi2:.3f}, p={p_chi2:.4f}")

table_refresh_abl = [[frozen_abl_pass, frozen_abl_n - frozen_abl_pass],
                      [refresh_abl_pass, refresh_abl_n - refresh_abl_pass]]
chi2_abl, p_chi2_abl, _, _ = stats.chi2_contingency(table_refresh_abl)
print(f"  Ablated arm: chi2={chi2_abl:.3f}, p={p_chi2_abl:.4f}")

# Save results
output = {
    "pass_rates": {name: {"pass": p, "total": n, "rate": round(p/n, 4),
                          "ci_95": [round(lo, 4), round(hi, 4)]}
                   for name, (p, n) in arms.items()
                          for lo, hi in [wilson_ci_manual(p, n)]},
    "pairwise_comparisons": {},
    "power_analysis": {
        "refresh_full_vs_ablated": {
            "observed_delta": round(observed_diff, 4),
            "min_detectable_80power": round(min_detectable, 4),
            "detectable": bool(observed_diff >= min_detectable),
            "n_per_arm": n1,
        },
        "frozen_full_vs_ablated": {
            "observed_delta": round(observed_diff_frozen, 4),
            "min_detectable_80power": round(min_detectable_frozen, 4),
            "detectable": bool(observed_diff_frozen >= min_detectable_frozen),
            "n_per_arm": n1f,
        },
    },
}
for a, b, label in pairs:
    p1, n1 = arms[a]
    p2, n2 = arms[b]
    diff, lo, hi = wilson_diff_ci(p1, n1, p2, n2)
    _, p_fisher = stats.fisher_exact([[p1, n1-p1], [p2, n2-p2]])
    output["pairwise_comparisons"][label] = {
        "delta": round(diff, 4),
        "ci_95": [round(lo, 4), round(hi, 4)],
        "p_fisher": round(p_fisher, 4),
    }

out_path = OUT / "power_analysis.json"
with open(out_path, "w") as f:
    json.dump(output, f, indent=2)
print(f"\nSaved to {out_path}")
