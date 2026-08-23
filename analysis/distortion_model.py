"""Fit QPU encoding-distortion models to real ibm_marrakesh data (v1.7 frozen data).

Models (P = observed P(1), w = target weight):
  M1 contraction:  P = 0.5 + alpha*(w - 0.5)          (reviewer proposal)
  M2 affine:       P = b + a*w                        (readout-channel-like)
Z-space linear:    Z_obs = d + c*Z_th                 (gain/bias decomposition)

Shot-noise reference: sigma ~= sqrt(p*(1-p)/8192) ~ 0.0055.
"""
import json
import math
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
SHOTS = 8192


def load(name):
    rows = json.loads((RAW / name).read_text())["rows"]
    return [(r["w"], r["p1"], r["z_theory"], r["z_emp"]) for r in rows]


def lsq(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    a = sxy / sxx
    return a, my - a * mx


def fit_m1(data):
    num = sum((w - 0.5) * (p - 0.5) for w, p, _, _ in data)
    den = sum((w - 0.5) ** 2 for w, p, _, _ in data)
    alpha = num / den
    resid = [p - (0.5 + alpha * (w - 0.5)) for w, p, _, _ in data]
    return alpha, resid


def fit_m2(data):
    a, b = lsq([w for w, _, _, _ in data], [p for _, p, _, _ in data])
    resid = [p - (b + a * w) for w, p, _, _ in data]
    return a, b, resid


def fit_z(data):
    c, d = lsq([zt for _, _, zt, _ in data], [ze for _, _, _, ze in data])
    resid = [ze - (d + c * zt) for _, _, zt, ze in data]
    return c, d, resid


def rms(resid):
    return math.sqrt(sum(r * r for r in resid) / len(resid))


def per_weight_alpha(data):
    out = {}
    for w, p, _, _ in data:
        if abs(w - 0.5) > 1e-12:
            out[w] = (p - 0.5) / (w - 0.5)
    return out


def report(tag, data):
    print(f"\n===== {tag} =====")
    print("per-weight alpha (M1):",
          {f"w={w}": round(a, 4) for w, a in sorted(per_weight_alpha(data).items())})
    alpha, r1 = fit_m1(data)
    print(f"M1 contraction : alpha={alpha:.4f}  residRMS={rms(r1):.4f}")
    a, b, r2 = fit_m2(data)
    print(f"M2 affine      : P={b:.4f}+{a:.4f}*w  residRMS={rms(r2):.4f}")
    c, d, rz = fit_z(data)
    print(f"Z-space linear : Z_obs={d:.4f}+{c:.4f}*Z_th  residRMS={rms(rz):.4f}")
    print(f"shot noise sigma ~ {math.sqrt(0.25 / SHOTS):.4f}")


def dev_table(bare, tw):
    tw_map = {round(w, 6): p for w, p, _, _ in tw}
    print("\n===== per-weight deviation |Z_emp - Z_th| =====")
    print(f"{'w':>5} {'bare':>8} {'twirl':>8} {'delta(twirl-bare)':>18}")
    for w, p, zt, ze in bare:
        e_b = abs(ze - zt)
        e_t = next(abs(ze2 - zt) for w2, _, zt2, ze2 in tw if abs(w2 - w) < 1e-9)
        mark = "IMPROVED" if e_t < e_b else "WORSE"
        print(f"{w:>5.2f} {e_b:>8.4f} {e_t:>8.4f} {e_t - e_b:>18.4f}  {mark}")


if __name__ == "__main__":
    ideal = load("qpu_validation_ideal.json")
    bare = load("qpu_validation_real.json")
    twirled = load("qpu_validation_real_mitigated.json")
    report("BARE (no mitigation)", bare)
    report("TWIRLED (16x readout twirling)", twirled)
    dev_table(bare, twirled)

    out = {
        "shots": SHOTS,
        "backend": "ibm_marrakesh",
        "source": "v1.7 frozen experiment results (jobs d9vbull..., d9vc6gt...)",
        "bare": {"alpha_per_weight": {str(k): v for k, v in per_weight_alpha(bare).items()},
                 **dict(zip(["slope_a", "intercept_b", "resid_rms"],
                            [*fit_m2(bare)[:2], rms(fit_m2(bare)[2])]))},
        "twirled": {"alpha_per_weight": {str(k): v for k, v in per_weight_alpha(twirled).items()},
                    **dict(zip(["slope_a", "intercept_b", "resid_rms"],
                               [*fit_m2(twirled)[:2], rms(fit_m2(twirled)[2])]))},
    }
    dest = Path(__file__).resolve().parent / "distortion_fits.json"
    dest.write_text(json.dumps(out, indent=2))
    print(f"\nsaved -> {dest}")
