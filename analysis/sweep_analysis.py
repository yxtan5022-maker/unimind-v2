"""Master analysis for tasks 3-5: distortion-model fitting on the sweep.

Outputs (per variant, pooled over repeats):
  M1 contraction  P = 0.5 + alpha*(w-0.5)
  M2 affine       P = b + a*w
  Z-space         Z_obs = d + c*Z_th        (gain c / bias d decomposition)
with repeat-level variability, plus E_noise(w) vs E_QPU(w) comparison and the
unpinned-placement diagnostic.
"""
import json
import math
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent / "data"
SWEEP = HERE / "qpu_sweep"
RAW = HERE / "raw"
OUT = Path(__file__).resolve().parent / "results"


def load_sweep(name):
    return json.loads((SWEEP / name).read_text())


def lsq(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    a = sxy / sxx
    return a, my - a * mx


def fits(rows):
    ws = [r["w"] for r in rows]
    p1 = [r["p1"] for r in rows]
    zt = [r["z_theory"] for r in rows]
    ze = [r["z_emp"] for r in rows]
    num = sum((w - 0.5) * (p - 0.5) for w, p in zip(ws, p1))
    den = sum((w - 0.5) ** 2 for w in ws)
    alpha = num / den
    r1 = [p - (0.5 + alpha * (w - 0.5)) for w, p in zip(ws, p1)]
    a2, b2 = lsq(ws, p1)
    r2 = [p - (b2 + a2 * w) for w, p in zip(ws, p1)]
    cz, dz = lsq(zt, ze)
    rz = [z - (dz + cz * t) for z, t in zip(ze, zt)]
    rms = lambda v: math.sqrt(sum(x * x for x in v) / len(v))
    return {"alpha": alpha,
            "affine_a": a2, "affine_b": b2,
            "z_gain": cz, "z_bias": dz,
            "rms_m1": rms(r1), "rms_m2": rms(r2), "rms_z": rms(rz),
            "max_dev": max(r["dev"] for r in rows),
            "sigma_shot": math.sqrt(0.25 / rows[0].get("shots", 8192))}


def main() -> int:
    OUT.mkdir(exist_ok=True)
    files = {
        "bare_pinned": ["sweep_bare_r{}.json".format(i) for i in range(3)],
        "twirled_pinned": ["sweep_twirled_r{}.json".format(i) for i in range(3)],
    }

    summary = {}
    print("== Sweep fits (pinned qubit 98 unless noted) ==")
    for tag, fnames in files.items():
        runs = [load_sweep(f) for f in fnames]
        per = [fits(r["rows"]) for r in runs]
        agg = {k: statistics.median(p[k] for p in per) if isinstance(per[0][k], float) else None
               for k in per[0]}
        spread = {k: (min(p[k] for p in per), max(p[k] for p in per))
                  for k in ("alpha", "affine_a", "affine_b", "max_dev")}
        placed = {r.get("placed_qubit") for r in runs}
        summary[tag] = {"per_repeat": per, "median": agg, "range": spread}
        print("\n{} (placed={}):".format(tag, placed))
        print("  M1 alpha      = {:.4f}  range {:.4f}-{:.4f}".format(
            agg["alpha"], *spread["alpha"]))
        print("  M2 P=b+a*w    : a={:.4f} b={:.4f}  rmsM1={:.4f} rmsM2={:.4f}".format(
            agg["affine_a"], agg["affine_b"], agg["rms_m1"], agg["rms_m2"]))
        print("  Z  gain={:.4f} bias={:.4f} rmsZ={:.4f}".format(
            agg["z_gain"], agg["z_bias"], agg["rms_z"]))
        print("  max_dev median={:.4f} range {:.4f}-{:.4f}  (shot sigma {:.4f})".format(
            agg["max_dev"], *spread["max_dev"], agg["sigma_shot"]))

    # unpinned diagnostic
    diag = load_sweep("sweep_bare_r3.json")
    df = fits(diag["rows"])
    summary["bare_unpinned_diag"] = {"placed_qubit": diag.get("placed_qubit"),
                                     "fits": df}
    print("\nunpinned diagnostic: placed on qubit {} -> max_dev={:.4f}, "
          "z_gain={:.4f}, z_bias={:.4f}".format(
              diag.get("placed_qubit"), df["max_dev"], df["z_gain"], df["z_bias"]))

    # matched noise model
    ln = load_sweep("sweep_localnoise.json")
    lf = fits(ln["rows"])
    summary["local_noise_model"] = {"fits": lf}
    print("matched local noise model (same qubit/calibration): "
          "max_dev={:.4f} z_gain={:.4f} z_bias={:.4f}".format(
              lf["max_dev"], lf["z_gain"], lf["z_bias"]))

    # E(w) comparison at shared weights (v1.5 grid vs new grid share only some)
    print("\n== E(w): noise-model vs bare-QPU vs twirled-QPU (medians over repeats) ==")
    bare_runs = [load_sweep(f)["rows"] for f in files["bare_pinned"]]
    tw_runs = [load_sweep(f)["rows"] for f in files["twirled_pinned"]]
    med = lambda rs, w: statistics.median(
        next(r["dev"] for r in run if abs(r["w"] - w) < 1e-9) for run in rs)
    ln_map = {round(r["w"], 2): r["dev"] for r in ln["rows"]}
    print("{:>6} {:>10} {:>10} {:>10}".format("w", "E_noise", "E_qpu_bare", "E_qpu_twi"))
    ratio_rows = []
    for w in [x / 20 for x in range(1, 20)]:
        en = ln_map.get(round(w, 2))
        eb, et = med(bare_runs, w), med(tw_runs, w)
        ratio_rows.append({"w": w, "E_noise": en, "E_bare": eb, "E_twirled": et})
        print("{:>6.2f} {:>10.4f} {:>10.4f} {:>10.4f}".format(
            w, en if en is not None else float("nan"), eb, et))
    import statistics as st
    ratios = [r["E_bare"] / r["E_noise"] for r in ratio_rows
              if r["E_noise"] and r["E_noise"] > 1e-4]
    print("\nmedian E_bare/E_noise ratio = {:.1f}x".format(st.median(ratios)))
    summary["E_table"] = ratio_rows
    summary["E_ratio_bare_over_noise_median"] = st.median(ratios)

    # v1.7 frozen reference
    v17b = json.loads((RAW / "qpu_validation_real.json").read_text())
    v17t = json.loads((RAW / "qpu_validation_real_mitigated.json").read_text())
    summary["v1_7_reference"] = {
        "bare_max_dev": v17b["max_dev"], "twirled_max_dev": v17t["max_dev"],
        "note": "v1.7 used free placement (no initial_layout); qubit not recorded"}
    print("\nv1.7 frozen reference: bare max_dev={:.3f} twirled={:.3f} "
          "(free placement, qubit unrecorded)".format(
              v17b["max_dev"], v17t["max_dev"]))

    (OUT / "sweep_analysis.json").write_text(json.dumps(summary, indent=2))
    print("\nsaved -> analysis/results/sweep_analysis.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
