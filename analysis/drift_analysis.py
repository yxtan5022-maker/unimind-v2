"""Multi-day calibration drift analysis (D0 -> D1).

Loads full 156-qubit calibration snapshots from data/drift/ and quantifies
cross-day rank stability, stale-model selection penalty, and a simple
detection threshold. Outputs analysis/results/drift_analysis.json.

Snapshots:
    D0 = data/drift/calib_2026-08-29.json   (fetched 2026-08-29T22:07; the
                                             snapshot behind tab:routing Run-2)
    D1 = data/drift/calib_2026-08-30.json   (fetched 2026-08-30T23:03)

Legacy single-qubit captures (documented provenance, git):
    q37, q98, q105, q119 at 2026-08-22/23 sweep time (git commit c53ee23).
"""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DRIFT = ROOT / "data" / "drift"
RES = ROOT / "analysis" / "results"
sys.path.insert(0, str(ROOT / "analysis"))
from utility_model import spearman_rho  # noqa: E402

D0_FILE = DRIFT / "calib_2026-08-29.json"
D1_FILE = DRIFT / "calib_2026-08-30.json"
OUT = RES / "drift_analysis.json"

PAPER_QUIRTS = [8, 109, 105, 53, 37, 27]

# Documented legacy per-qubit readout totals (git commit c53ee23, 2026-08-22/23
# sweep-time calibration). Included only as a cross-reference, not as a fresh
# full-snapshot measurement.
LEGACY_CAPTURES = [
    {"capture": "2026-08-22/23 (git c53ee23, Run-1 sweep-time)", "rows": [
        {"q": 98, "C": 0.00439453125}, {"q": 20, "C": 0.01513671875},
        {"q": 105, "C": 0.02392578125}, {"q": 31, "C": 0.04931640625},
        {"q": 119, "C": 0.3201171875}, {"q": 37, "C": 0.82177734375}]},
]


def load_capture(path):
    d = json.loads(path.read_text(encoding="utf-8"))
    c = {e["q"]: e["readout_total"] for e in d["qubits"]}
    return c, d.get("last_update_date"), d.get("fetched_at")


def rank_map(c):
    order = sorted(c, key=c.get)
    return {q: i + 1 for i, q in enumerate(order)}, len(order)


def jaccard(a, b):
    return len(set(a) & set(b)) / max(1, len(set(a) | set(b)))


def main():
    from scipy import stats
    c0, d0_upd, d0_fetched = load_capture(D0_FILE)
    c1, d1_upd, d1_fetched = load_capture(D1_FILE)

    r0, n = rank_map(c0)
    r1, _ = rank_map(c1)
    qubits = sorted(c0)

    sr = stats.spearmanr([c0[q] for q in qubits], [c1[q] for q in qubits])
    kt = stats.kendalltau([c0[q] for q in qubits], [c1[q] for q in qubits])
    g_rho, g_p = sr.correlation, float(sr.pvalue)
    tau_norm = float(kt.correlation)

    top10_0 = sorted(qubits, key=lambda q: c0[q])[:10]
    top10_1 = sorted(qubits, key=lambda q: c1[q])[:10]
    top3_0 = top10_0[:3]
    top3_1 = top10_1[:3]

    stale_set = top3_0
    fresh_set = top3_1
    top10_j = jaccard(top10_0, top10_1)
    stale_best_dC = c1[stale_set[0]] - c0[stale_set[0]]
    trigger_fired = bool(top10_j < 0.5 or stale_best_dC > 0.005)
    stale_penalty = []
    for q in stale_set:
        stale_penalty.append({"q": q, "C_rank0": c0[q], "C_evalD1": c1[q],
                              "rank0": r0[q], "rank1": r1[q],
                              "delta": round(c1[q] - c0[q], 5)})
    fresh_picks = [{"q": q, "C_evalD1": c1[q], "rank1": r1[q]} for q in fresh_set]
    best_stale_C_d1 = max(s["C_evalD1"] for s in stale_penalty)
    best_fresh_C_d1 = min(p["C_evalD1"] for p in fresh_picks)
    stale_best_rank_d1 = min(r1[q] for q in stale_set)
    stale_max_penalty = round(c1[stale_set[0]] - c1[fresh_set[0]], 5)

    deltas = {q: abs(c1[q] - c0[q]) for q in qubits}
    dvals = sorted(deltas.values())
    n = len(dvals)
    def pct(p):
        return round(dvals[min(n - 1, int(p * n))], 5)
    med_delta = pct(0.5)
    p90 = pct(0.90)
    p95 = pct(0.95)
    max_delta = round(dvals[-1], 5)
    max_delta_q = max(deltas, key=deltas.get)
    frac_gt = {t: round(sum(1 for v in deltas.values() if v > t) / len(deltas), 4)
               for t in (0.005, 0.01, 0.02)}
    med_ratio = sorted(c1[q] / c0[q] for q in qubits)[n // 2]

    paper_rows = []
    for q in PAPER_QUIRTS:
        paper_rows.append({
            "q": q, "C_D0": c0[q], "C_D1": c1[q],
            "rank_D0_156": r0[q], "rank_D1_156": r1[q],
            "abs_delta": round(abs(c1[q] - c0[q]), 5),
            "ratio": round(c1[q] / c0[q], 3)})

    result = {
        "method": "two full 156-qubit ibm_marrakesh readout-total captures",
        "snapshots": {
            "D0": {"file": str(D0_FILE), "device_update": d0_upd, "fetched": d0_fetched},
            "D1": {"file": str(D1_FILE), "device_update": d1_upd, "fetched": d1_fetched}},
        "n_qubits": n,
        "rank_stability": {
            "spearman_rho_156": round(g_rho, 4), "spearman_p": round(g_p, 4),
            "kendall_tau": round(tau_norm, 4),
            "top10_jaccard": round(jaccard(top10_0, top10_1), 3),
            "top10_c0": top10_0, "top10_c1": top10_1},
        "paper_qubits": {"rows": paper_rows},
        "stale_vs_fresh_selection": {
            "stale_set_rank0_top3": stale_set,
            "stale_rows": stale_penalty,
            "fresh_set_D1_top3": fresh_set,
            "fresh_rows": fresh_picks,
            "stale_best_C_on_D1": round(best_stale_C_d1, 5),
            "fresh_best_C_on_D1": round(best_fresh_C_d1, 5),
            "stale_best_rank_on_D1_156": stale_best_rank_d1,
            "worst_pick_delta": stale_max_penalty},
        "drift_magnitude": {
            "median_abs_delta_C": med_delta, "p90_abs_delta": p90,
            "p95_abs_delta": p95, "max_abs_delta": max_delta,
            "max_delta_q": max_delta_q,
            "frac_qubits_absdelta_gt": frac_gt,
            "median_C_ratio_d1_over_d0": round(med_ratio, 3)},
        "detection_rule": {
            "trigger": "refresh when jaccard(top10_D0, top10_D1) < 0.5 OR "
                       "best_qubit(D0).C increases by > 0.005 absolute on D1",
            "D0_to_D1_top10_jaccard": round(top10_j, 3),
            "D0_to_D1_best_C_increase": round(stale_best_dC, 5),
            "D0_to_D1_triggered": trigger_fired},
        "legacy_captures": LEGACY_CAPTURES,
    }
    with OUT.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=1, ensure_ascii=False)

    print("== drift_analysis (D0=2026-08-29 -> D1=2026-08-30, n=%d qubits) ==" % n)
    print("Spearman rho(156) = %.4f (p=%.4f); Kendall tau = %.4f" % (g_rho, g_p, tau_norm))
    print("top-10 Jaccard = %.3f; top-10 D0=%s" % (jaccard(top10_0, top10_1), top10_0))
    print("top-10 D1 =%s" % top10_1)
    print("paper qubits C(D0 -> D1):")
    for r in paper_rows:
        print("  q%-5d %.5f -> %.5f  rank %d -> %d" % (r["q"], r["C_D0"], r["C_D1"],
                                                       r["rank_D0_156"], r["rank_D1_156"]))
    print("stale(pick D0 %) vs fresh(D1) top-3:")
    print("  stale: " + ", ".join("q%d=%.4f" % (s["q"], s["C_evalD1"]) for s in stale_penalty))
    print("  fresh: " + ", ".join("q%d=%.4f" % (p["q"], p["C_evalD1"]) for p in fresh_picks))
    print("  staleBest_D1_C=%.4f (rank %d) vs freshBest_D1_C=%.4f" %
          (best_stale_C_d1, stale_best_rank_d1, best_fresh_C_d1))
    print("drift: median |dC|=%.4f, p95=%.4f, max=%.4f (q%d); median C ratio=%.3f" %
          (med_delta, p95, max_delta, max_delta_q, med_ratio))
    print("trigger fired:", result["detection_rule"]["D0_to_D1_triggered"])
    print("written ->", OUT)


if __name__ == "__main__":
    main()