"""Task 2 -- Failure taxonomy mining over frozen v1.7 llm_reliability results.

Classifies every task row into an outcome PATH, builds the
injected-fault -> outcome transition matrix (recovery rate per fault class),
latency/cost per path, and Wilson 95% CIs for success rates.
No re-running of experiments: pure post-processing of existing JSONs.
"""
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent / "data"
RAW = HERE / "raw"
OUT = Path(__file__).resolve().parent / "results"
FILES = {
    0.5: "llm_reliability_mock_q0.5_60.json",
    0.7: "llm_reliability_mock_q0.7_60.json",
    0.9: "llm_reliability_mock_q0.9_60.json",
    1.0: "llm_reliability_mock_q1.0_60.json",
}


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def classify(r):
    """Outcome path of one valid-task row."""
    res = r.get("result") or ""
    if r.get("fallback"):
        return "fallback_ok" if r["success"] else "fallback_failed"
    if r.get("heal"):
        return "healed" if r["success"] else "heal_failed"
    if r.get("validation_failure"):
        return "validation_rejected"
    if "LLM_EXECUTED" in res:
        return "first_pass" if r["success"] else "exec_failed"
    return "other_failed" if not r["success"] else "other_ok"


def fault_signature(r):
    """Which injected corruption surfaced, inferred from the executor text."""
    res = (r.get("result") or "").lower()
    if r.get("validation_failure") or "import" in res and ("whitelist" in res or "not allowed" in res):
        return "import_violation"
    if "zerodivision" in res:
        return "runtime_zero_division"
    if "undefined_name" in res or "nameerror" in res:
        return "name_error"
    if "syntax" in res or "invalid syntax" in res or "compile" in res:
        return "syntax_error"
    if r.get("heal") or r.get("invalid_code") or r.get("retries", 0) > 0:
        return "unspecified_broken_code"
    return None


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report, tables = {}, {}

    # ---- adversarial rejection (all quality levels pooled & per level) ----
    adv = {}
    for q, fn in FILES.items():
        d = json.loads((RAW / fn).read_text())
        rows = [r for r in d["rows"] if r["class"] == "adversarial"]
        k = sum(1 for r in rows if r["success"])
        lo, hi = wilson(k, len(rows))
        adv[q] = {"n": len(rows), "rejected": k,
                  "ci95": [round(lo, 4), round(hi, 4)]}
    report["adversarial_rejection"] = adv

    # ---- per-quality outcome distribution + success CI ----
    dist = {}
    for q, fn in FILES.items():
        d = json.loads((RAW / fn).read_text())
        rows = [r for r in d["rows"] if r["class"] == "valid"]
        n = len(rows)
        cnt = Counter(classify(r) for r in rows)
        succ = sum(1 for r in rows if r["success"])
        lo, hi = wilson(succ, n)
        dist[q] = {"n": n, "success": succ, "ci95": [round(lo, 4), round(hi, 4)],
                   "paths": dict(cnt)}
    report["valid_outcomes"] = dist

    # ---- fault -> outcome transition matrix (pooled over q<1.0 levels) ----
    trans = defaultdict(Counter)
    lat_by_path = defaultdict(list)
    calls_by_path = defaultdict(list)
    for q, fn in FILES.items():
        d = json.loads((RAW / fn).read_text())
        for r in d["rows"]:
            if r["class"] != "valid":
                continue
            path = classify(r)
            lat_by_path[path].append(r.get("latency_ms"))
            calls_by_path[path].append(r.get("llm_calls"))
            if q == 1.0:
                continue  # no injected faults at perfect quality
            f = fault_signature(r)
            if f:
                trans[f][path] += 1
    tables["fault_to_outcome"] = {f: dict(c) for f, c in sorted(trans.items())}

    recov = {}
    print("\n== Fault -> recovery (pooled q=0.5/0.7/0.9, n=180 valid tasks) ==")
    print(f"{'fault class':<24} {'n':>4} {'recovered':>10} {'rate':>7} {'CI95':>17}")
    for f, c in sorted(trans.items()):
        bad = {"heal_failed", "fallback_failed", "exec_failed", "other_failed"}
        n = sum(c.values())
        ok = sum(v for kk, v in c.items() if kk not in bad)
        lo, hi = wilson(ok, n)
        recov[f] = {"n": n, "recovered": ok, "rate": round(ok / n, 4),
                    "ci95": [round(lo, 4), round(hi, 4)]}
        print(f"{f:<24} {n:>4} {ok:>10} {ok/n:>6.1%} [{lo:.3f},{hi:.3f}]")
    tables["recovery_rate"] = recov

    # ---- latency / LLM-call cost by path ----
    cost = {}
    for path in sorted(lat_by_path):
        xs = [x for x in lat_by_path[path] if x is not None]
        cs = [x for x in calls_by_path[path] if x is not None]
        xs.sort()
        med = xs[len(xs) // 2] if xs else float("nan")
        cost[path] = {"n": len(xs), "median_ms": round(med, 3),
                      "mean_llm_calls": round(sum(cs) / len(cs), 3) if cs else None}
    tables["cost_per_path"] = cost

    dest_json = OUT / "failure_taxonomy.json"
    dest_md = OUT / "failure_taxonomy.md"
    dest_json.write_text(json.dumps({"report": report, "tables": tables},
                                    indent=2))

    lines = ["# Failure taxonomy -- v1.7 frozen data (mined, not re-run)", ""]
    lines.append("## Valid-task outcome paths vs mock quality\n")
    lines.append("| q | n | first_pass | healed | fallback_ok | validation_rejected | failed | success [CI95] |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for q in sorted(dist):
        e = dist[q]
        p = e["paths"]
        failed = sum(v for kk, v in p.items() if "fail" in kk)
        lines.append(
            f"| {q} | {e['n']} | {p.get('first_pass',0)} | {p.get('healed',0)} "
            f"| {p.get('fallback_ok',0)} | {p.get('validation_rejected',0)} | {failed} "
            f"| {e['success']}/{e['n']} [{e['ci95'][0]:.2f},{e['ci95'][1]:.2f}] |")
    lines.append("\n## Injected fault -> recovery\n")
    lines.append("| fault class | n | recovered | rate | CI95 |")
    lines.append("|---|---|---|---|---|")
    for f, e in recov.items():
        lines.append(f"| {f} | {e['n']} | {e['recovered']} "
                     f"| {e['rate']:.1%} | [{e['ci95'][0]:.2f},{e['ci95'][1]:.2f}] |")
    lines.append("\n## Cost per outcome path (all qualities pooled)\n")
    lines.append("| path | n | median latency ms | mean LLM calls |")
    lines.append("|---|---|---|---|")
    for p_, e in cost.items():
        lines.append(f"| {p_} | {e['n']} | {e['median_ms']} | {e['mean_llm_calls']} |")
    dest_md.write_text("\n".join(lines) + "\n")

    print(json.dumps(report["valid_outcomes"], indent=1))
    print(f"\nsaved -> {dest_json.name}, {dest_md.name}")


if __name__ == "__main__":
    main()
