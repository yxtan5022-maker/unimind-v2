"""Task 2 (v2) -- instrumented reliability re-run: exact injected-fault taxonomy.

Re-runs the v1.7 mock reliability benchmark with call-level logging, so
P(f_i), RecoveryRate(f_i) and heal-chain behaviour are measured exactly
instead of inferred from clipped result strings. Mock mode: local, free,
seeded.
"""
import json
import sys
import io
import contextlib
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mock_llm import (  # noqa: E402
    FAULT_CLASS, InstrumentedMock, first_injected_fault, generate_tasks,
    run_one_config, wilson,
)

OUT = Path(__file__).resolve().parent / "results"
GRID = [(q, s) for q in (0.5, 0.7, 0.9) for s in (42, 43, 44)]
N_VALID, N_ADV, FAILRATE = 200, 20, 0.1


def main() -> int:
    OUT.mkdir(exist_ok=True)
    pooled_faults = Counter()
    fault_recovered = Counter()
    fault_total = Counter()
    path_counts = Counter()
    lat_by_path = defaultdict(list)
    per_run = []

    for q, seed in GRID:
        tasks = generate_tasks(N_VALID, N_ADV, seed)
        mock = InstrumentedMock(q, FAILRATE, seed)
        from bridge.umos_link import UMOSLink
        link = UMOSLink("reliability-v2")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rows = run_one_config(link, mock, tasks)

        valid = [r for r in rows if r["class"] == "valid"]
        succ = sum(r["success"] for r in valid)
        for r in valid:
            path_counts[r["path"]] += 1
            lat_by_path[r["path"]].append(r["latency_ms"])
            fi = first_injected_fault(mock, r["id"])
            if fi is not None:
                cls = FAULT_CLASS[fi]
                pooled_faults[cls] += 1
                fault_total[cls] += 1
                if r["success"]:
                    fault_recovered[cls] += 1

        lo, hi = wilson(succ, len(valid))
        per_run.append({"q": q, "seed": seed, "n_valid": len(valid),
                        "success": succ, "ci95": [lo, hi]})
        print("q={} seed={}: {}/{} = {:.1f}% [ {:.3f}, {:.3f} ]".format(
            q, seed, succ, len(valid), 100 * succ / len(valid), lo, hi))

    print("\n== Injected-fault recovery (pooled, q<1.0) ==")
    recov = {}
    for cls in sorted(fault_total):
        n, ok = fault_total[cls], fault_recovered[cls]
        lo, hi = wilson(ok, n)
        recov[cls] = {"n": n, "recovered": ok, "rate": round(ok / n, 4),
                      "ci95": [round(lo, 4), round(hi, 4)]}
        print("{:<24} n={:<4} recovered={:<4} {:.1%} [{:.3f},{:.3f}]".format(
            cls, n, ok, ok / n, lo, hi))

    cost = {}
    for p_, xs in sorted(lat_by_path.items()):
        xs.sort()
        cost[p_] = {"n": len(xs), "median_ms": round(xs[len(xs) // 2], 3)}

    out = {"grid": GRID, "failrate": FAILRATE, "per_run": per_run,
           "paths": dict(path_counts), "recovery": recov, "cost": cost}
    (OUT / "reliability_instrumented.json").write_text(json.dumps(out, indent=2))
    print("\nsaved -> analysis/results/reliability_instrumented.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
