"""RQ4 -- Exact absorbing-chain reliability model for the UniMind pipeline.

Derives closed-form path probabilities for the orchestration pipelines used
in E-03/E-04/E-06 and validates them against the logged experimental data.

Pipeline semantics (from bridge/umos_link.py, bridge/healer.py,
experiments/llm_reliability.py):

  Generation  : up to K=3 iid draws; stop at first non-None.
                Draw categories: None w.p. f, ground truth w.p. g,
                broken w.p. r (= 1 - g - f), with the mock's clipping rule
                g = clip(q + f, f, 1) - f  (so g = q whenever q + f <= 1).
  Validation  : static-analysis gate. NOTE: none of the six broken
                templates matches any blocked pattern, so the gate never
                fires on valid-task fault injection (it only catches the
                adversarial payload). Formally S0 == S1 on this benchmark.
  Execution   : gt always succeeds; broken always raises.
  Healing     : fresh draws H=4 max; ANY None aborts immediately (fail);
                each broken draw consumes one slot; success on first gt.
                rho_h = g * (1 - r^H) / (1 - r).
  Fallback    : deterministic template, succeeds iff intent covered
                (coverage c: narrow = bell-keyword match, full = 1).

Path probabilities (valid tasks):
  P(no_code)     = f^3
  P(first_pass)  = g * G,          G = 1 + f + f^2
  P(broken_first)= r * G           -> enters healing
  P(healed)      = r * G * rho_h
  P(heal_failed) = r * G * (1-rho_h)
  P(fallback_ok) = f^3 * c         (S3/S3X only)
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

RES = Path(__file__).resolve().parent / "results"
K_GEN, H_HEAL = 3, 4


def mock_probs(q: float, f: float) -> tuple[float, float, float]:
    """Per-call category probabilities under InstrumentedMock semantics."""
    lo, hi = min(f, 1.0), 1.0
    g = min(max(q + f, lo), hi) - f
    g = max(g, 0.0)
    r = max(1.0 - g - f, 0.0)
    return f, g, r


def geom_cap(p_success_each_round: float, rounds: int) -> float:
    """P(at least one success in `rounds` iid trials)."""
    return 1.0 - (1.0 - p_success_each_round) ** rounds


def rho_heal_structural(g: float, r: float, h: int = H_HEAL) -> float:
    """Healing recovery | entered: gt before any None, <= h draws."""
    if r >= 1.0:
        return 0.0
    return g * (1.0 - r ** h) / (1.0 - r)


def ablation_paths(q: float, f: float, stage: str, coverage: float = 0.0):
    """Exact path probabilities for one AblationLink stage."""
    _, g, r = mock_probs(q, f)
    G = sum(f ** k for k in range(K_GEN))
    out = {
        "first_pass": g * G,
        "broken_first": r * G,
        "healed": r * G * rho_heal_structural(g, r),
        "heal_failed": r * G * (1 - rho_heal_structural(g, r)),
        "no_code": f ** K_GEN,
    }
    if stage in ("S3", "S3X"):
        cov = {"S3": coverage, "S3X": 1.0}[stage]
        out["fallback_ok"] = out["no_code"] * cov
        out["no_code"] -= out["fallback_ok"]
    return out


def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def check(name: str, pred: float, k: int, n: int) -> dict:
    lo, hi = wilson(k, n)
    obs = k / n
    # degenerate zero-event cells: Wilson interval excludes 0 by construction,
    # so treat pred==obs==0 as agreement rather than a CI violation
    inside = (lo <= pred <= hi) or (pred == 0.0 and k == 0)
    return {"cell": name, "predicted": round(pred, 4), "observed": round(obs, 4),
            "k": k, "n": n, "ci95": [round(lo, 4), round(hi, 4)],
            "pred_in_ci": inside}


# Narrow-stage effective coverage, derived from the task mix and the
# production fallback's no-match branch: the returned code embeds the raw
# intent inside a single-quoted string literal, so any intent containing
# an apostrophe ('result', 'qc') becomes a SyntaxError at execution.
# Under the 9-kind benchmark mix only `bell` (keyword match -> real
# template) and `angle` (apostrophe-free intent) yield executing code.
NARROW_COVERAGE = 2.0 / 9.0


def validate_quality() -> list[dict]:
    """E-03: ablation_quality.json, stages S0-S2, q in {.5,.7,.9}, f=0.1."""
    rows = json.loads((RES / "ablation_quality.json").read_text())
    f = 0.1
    checks = []
    agg: dict[tuple, dict] = {}
    for r in rows:
        key = (r["stage"], r["q"])
        a = agg.setdefault(key, {"n": 0, "success": 0, "paths": {}})
        a["n"] += r["n_valid"]
        a["success"] += r["success"]
        for p_, v in r.get("paths", {}).items():
            a["paths"][p_] = a["paths"].get(p_, 0) + v
    for (stage, q), a in sorted(agg.items()):
        m = ablation_paths(q, f, stage)
        if stage in ("S0", "S1"):
            pred_succ = m["first_pass"]
        elif stage == "S2":
            pred_succ = m["first_pass"] + m["healed"]
        else:
            pred_succ = None
        if pred_succ is not None:
            checks.append(check(
                "E03 {} q={} success".format(stage, q), pred_succ,
                a["success"], a["n"]))
        # component paths for S2
        if stage == "S2":
            for comp in ("first_pass", "healed"):
                k = a["paths"].get(comp, 0)
                checks.append(check(
                    "E03 S2 q={} path={}".format(q, comp), m[comp], k, a["n"]))
    return checks


def validate_stress() -> dict:
    """E-03 stress + E-06 stress2: S2/S3(narrow)/S3X under availability stress."""
    out = {}
    for fname, stages in (("ablation_stress.json", ("S2", "S3")),
                          ("ablation_stress2.json", ("S2", "S3X"))):
        rows = json.loads((RES / fname).read_text())
        for stg in stages:
            sub = [r for r in rows if r["stage"] == stg]
            for fr in sorted({r["failrate"] for r in sub}):
                runs = [r for r in sub if abs(r["failrate"] - fr) < 1e-9]
                n = sum(r["n_valid"] for r in runs)
                succ = sum(r["success"] for r in runs)
                m = ablation_paths(0.7, fr, stg)
                if stg == "S2":
                    pred = m["first_pass"] + m["healed"]
                elif stg == "S3":
                    pred = (m["first_pass"] + m["healed"]
                            + fr ** K_GEN * NARROW_COVERAGE)
                    fb_ok = sum(r["paths"].get("fallback_ok", 0) for r in runs)
                    exp_fb = n * fr ** K_GEN * NARROW_COVERAGE
                    out.setdefault("narrow_fallback_events", []).append(
                        {"failrate": fr, "predicted": round(exp_fb, 2),
                         "observed": fb_ok})
                else:
                    pred = m["first_pass"] + m["healed"] + fr ** K_GEN
                out.setdefault("cells", []).append(
                    check("E06 {} fr={}".format(stg, fr), pred, succ, n))
    return out


def decomposition() -> list[dict]:
    """Section 5.13 correction: naive-independence vs structural vs empirical."""
    rows = []
    qual = json.loads((RES / "ablation_quality.json").read_text())
    for q in (0.5, 0.7):
        runs = [r for r in qual if r["stage"] == "S2" and abs(r["q"] - q) < 1e-9]
        hl = sum(r["paths"].get("healed", 0) for r in runs)
        fl = sum(r["paths"].get("failed_other", 0) for r in runs)
        n_ev = hl + fl
        emp = hl / n_ev if n_ev else float("nan")
        f = 0.1
        _, g, r_ = mock_probs(q, f)
        struct = rho_heal_structural(g, r_)
        naive = geom_cap(q, H_HEAL)
        lo, hi = wilson(hl, n_ev)
        rows.append({
            "q": q, "heal_events": n_ev,
            "naive_indep": round(naive, 4),
            "structural_exact": round(struct, 4),
            "empirical": round(emp, 4),
            "ci95": [round(lo, 4), round(hi, 4)],
            "struct_in_ci": lo <= struct <= hi,
            "naive_gap_pp": round(100 * (naive - emp), 1),
            "residual_pp": round(100 * (emp - struct), 1),
        })
    return rows


def interventions() -> list[dict]:
    """Policy-variant predictions (H4.3 redefined): what actually moves rho."""
    q, f = 0.5, 0.1
    _, g, r = mock_probs(q, f)
    base = rho_heal_structural(g, r)
    out = [{"variant": "baseline (abort-on-None, H=4)", "rho": round(base, 4)}]

    # V1: treat None as a wasted attempt instead of aborting the loop
    p_any = 1.0 - (r + f) ** H_HEAL
    out.append({"variant": "None wastes a slot (no abort), H=4",
                "rho": round(p_any, 4),
                "delta_pp": round(100 * (p_any - base), 1)})

    # V2: keep abort-on-None but extend budget to H=8
    v2 = g * (1 - r ** 8) / (1 - r)
    out.append({"variant": "budget H=8 (abort retained)", "rho": round(v2, 4),
                "delta_pp": round(100 * (v2 - base), 1)})

    # V3: heterogeneous healer (decorrelation proxy): healer quality q_h = 0.9
    qh = 0.9
    _, g_h, r_h = mock_probs(qh, f)
    v3 = g_h * (1 - r_h ** H_HEAL) / (1 - r_h)
    out.append({"variant": "healer quality q_h=0.9 (gen q=0.5)",
                "rho": round(v3, 4), "delta_pp": round(100 * (v3 - base), 1)})
    return out


def main() -> int:
    rep = {
        "quality_checks": validate_quality(),
        "stress": validate_stress(),
        "decomposition": decomposition(),
        "interventions_q05_fr01": interventions(),
    }
    n_pass = sum(1 for c in rep["quality_checks"] if c["pred_in_ci"])
    n_tot = len(rep["quality_checks"])
    print("== E-03 quality grid: {}/{} cells have model prediction inside "
          "Wilson 95% CI ==".format(n_pass, n_tot))
    for c in rep["quality_checks"]:
        flag = "PASS" if c["pred_in_ci"] else "FAIL"
        print("{} {:<34} pred={:.3f} obs={:.3f} ci=({:.3f},{:.3f})".format(
            flag, c["cell"], c["predicted"], c["observed"], *c["ci95"]))

    print("\n== Availability stress ==")
    for c in rep["stress"]["cells"]:
        flag = "PASS" if c["pred_in_ci"] else "FAIL"
        print("{} {:<28} pred={:.3f} obs={:.3f} ci=({:.3f},{:.3f})".format(
            flag, c["cell"], c["predicted"], c["observed"], *c["ci95"]))
    print("narrow-fallback events (n*f^3*c, c=2/9):",
          rep["stress"].get("narrow_fallback_events"))

    print("\n== rho_heal decomposition (section 5.13 correction) ==")
    for row in rep["decomposition"]:
        print("q={q}: naive={naive_indep} structural={structural_exact} "
              "empirical={empirical} ci={ci95} struct_in_ci={struct_in_ci} "
              "(naive gap {naive_gap_pp}pp, residual {residual_pp}pp)".format(**row))

    print("\n== Policy interventions (q=0.5, f=0.1) ==")
    for row in rep["interventions_q05_fr01"]:
        print("{:<40} rho={}".format(row["variant"], row["rho"]))

    (RES / "reliability_model.json").write_text(json.dumps(rep, indent=2))
    print("\nsaved -> analysis/results/reliability_model.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
