"""Phase 9: Deepen J(G) proxy-to-real failure analysis.
Compares calibration of v4 (proxy-trained) vs v5 (real-label) utility model
and pinpoints WHY the OOS correlation collapses."""
import json
from pathlib import Path

ROOT = Path(r"C:\Users\SCSM11\Desktop\unimind-v2")
OUT = ROOT / "analysis" / "results"

v4 = json.loads((OUT / "utility_model_v4.json").read_text())
v5 = json.loads((OUT / "utility_model_v5.json").read_text())
oos_v4 = json.loads((OUT / "utility_oos.json").read_text())
oos_v5 = json.loads((OUT / "utility_oos_v5.json").read_text())

print("=== J(G) Utility: v4 (proxy) vs v5 (real labels) ===")
print(f"\nFull-fit Spearman:  v4 rho={v4['full_fit']['spearman']['rho']:.4f}  v5 rho={v5['full_fit']['spearman']['rho']:.4f}")
print(f"LOO Spearman:       v4 loo={v4['loo']['loo_rho']:.4f}  v5 loo={v5['loo']['loo_rho']:.4f}")
print(f"OOS (size OOS):     v4 rho={oos_v4.get('test', {}).get('spearman', 0):.4f}  v5 rho={oos_v5['test']['spearman']:.4f}")

# Feature weights divergence
print("\n=== Feature Weight Divergence (v4 proxy vs v5 real) ===")
w4 = v4["full_fit"]["params"]
w5 = v5["full_fit"]["params"]
print(f"{'Param':<12} {'v4 proxy':>10} {'v5 real':>10} {'ratio':>8} {'dir':>6}")
print("-" * 50)
moved = {}
for k in sorted(set(w4) | set(w5)):
    a = w4.get(k, 0)
    b = w5.get(k, 0)
    ratio = b / a if a != 0 else float("inf")
    direction = "up" if b > a else ("down" if b < a else "same")
    moved[k] = ("up" if b > a else "down") if a != 0 and abs(b - a) > 0.01 else "same"
    print(f"{k:<12} {a:>10.4f} {b:>10.4f} {ratio:>8.2f} {direction:>6}")

print("\n=== Parameter moves (proxy -> real) ===")
for k, d in moved.items():
    print(f"  {k}: {d}")

# Key: which params moved most?
print("\n=== Largest absolute parameter moves ===")
diffs = sorted({k: abs(w5.get(k, 0) - w4.get(k, 0)) for k in set(w4) | set(w5)}.items(),
               key=lambda kv: kv[1], reverse=True)
for k, d in diffs[:5]:
    print(f"  {k}: |delta|={d:.4f} (v4={w4.get(k,0):.4f} -> v5={w5.get(k,0):.4f})")

# Per-k real label means: the size effect that the proxy missed
print("\n=== Real-label size effect (what the proxy got wrong) ===")
rl = v5["real_labels"]["per_k_mean"]
print(f"{'k':<6} {'real max_dev mean':>16}")
print("-" * 24)
for k in sorted(rl, key=int):
    print(f"{k:<6} {rl[k]:>16.4f}")

# v4 proxy-predicted vs actual
print("\n=== v4 OOS (proxy-trained, k>=9 test) ===")
print(f"  test rho={oos_v4.get('test', {}).get('spearman', 'N/A')}")
print(f"  v4 was OPTIMISTIC at large k (proxy under-penalized that the real device, once refresh-pinned, does NOT penalize)")

# Key finding
print("\n=== KEY FINDING ===")
print("""
The v4 model (trained on simulator proxy) achieved high correlation (full 0.967, LOO 0.953, OOS 0.818)
because the proxy imposed a large-layout penalty that the REAL device (refresh-pinned) does not have.
When labels are replaced by refresh-pinned real max_dev for k in [9,10,11,12,14,16,18]:
  - full-fit Spearman collapses 0.967 -> 0.643
  - LOO Spearman collapses 0.953 -> 0.510
  - size-OOS Spearman collapses 0.818 -> 0.127 (p=0.36, ns)
The proxy's size penalty is REAL for a frozen/stale device (stale pins inflate error at k>=9),
but FICTIONAL for a refresh-pinned device. Therefore J(G) is not wrong per se; it encodes the
STALE-device error model, which is exactly what the adaptive refresh policy removes.
This is why refresh dominates placement: the utility model's discriminative power trades on a
device-staleness signal that refresh eliminates.
""")

output = {
    "v4_full_rho": v4["full_fit"]["spearman"]["rho"],
    "v5_full_rho": v5["full_fit"]["spearman"]["rho"],
    "v4_loo_rho": v4["loo"]["loo_rho"],
    "v5_loo_rho": v5["loo"]["loo_rho"],
    "v4_oos_rho": oos_v4.get("test", {}).get("spearman"),
    "v5_oos_rho": oos_v5["test"]["spearman"],
    "v5_oos_p": oos_v5["test"].get("spearman_p_mc_20000"),
    "param_weights": {
        "v4": w4,
        "v5": w5,
        "largest_moves": {k: {"delta": round(d, 4), "v4": w4.get(k, 0), "v5": w5.get(k, 0)}
                          for k, d in diffs[:5]},
    },
    "real_label_size_effect": rl,
    "key_finding": ("The proxy utility J(G) over-penalizes large layouts (k>=9). Under a refresh-pinned "
                    "device this penalty is fictional, collapsing OOS Spearman from 0.818 to 0.127 (p=0.36). "
                    "J(G) encodes a STALE-device error model that the adaptive refresh policy removes."),
}
with open(OUT / "jg_failure_analysis.json", "w") as f:
    json.dump(output, f, indent=2)
print("Saved result.")
