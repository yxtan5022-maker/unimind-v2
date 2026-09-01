"""E-08 (RQ3) -- Hardware-aware routing: C(q) score, stratified validation.

Parts
-----
local    fetch full calibration snapshot of every usable qubit, rank by
         C(q), verify anchors (q98/q37 vs E-05), select a stratified
         validation set, microbenchmark selector + transpile overhead.
qpu      one bare 19-weight pinned sweep job per selected qubit
         (resume-safe: existing result files are skipped).
analyze  per-qubit max_dev + affine fit; rank correlation between C(q)
         and measured distortion; charter verdicts H3.1/H3.2/H3.3.

C(q) definition (pre-registered in EXPERIMENTS.md E-08):
  primary key  : total readout assignment error p01 + p10
                 (E-05 showed readout dominates single-qubit distortion;
                  no weights are fitted on the two anchor qubits)
  tiebreak     : -min(T1, T2)
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from itertools import permutations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from qpu_sweep import WEIGHTS, SHOTS, SEED, build_circuit, rotation_angle  # noqa: E402

RES = Path(__file__).resolve().parent / "results"
SWEEP_DIR = Path(__file__).resolve().parent.parent / "data" / "qpu_sweep"
BACKEND = "ibm_marrakesh"
ANCHOR_E05 = {98: 0.00439453125, 37: 0.82177734375}
TOL = 0.05


# --------------------------------------------------------------- snapshot
def fetch_table(backend):
    from qpu_sweep import _prop
    props = backend.properties()
    rows = []
    for qi in range(backend.num_qubits):
        p01 = _prop(props, qi, "prob_meas0_prep1")
        p10 = _prop(props, qi, "prob_meas1_prep0")
        if p01 is None or p10 is None:
            continue
        try:
            sx = props.gate_error("sx", [qi])
        except Exception:
            sx = None
        rows.append({"q": qi, "p01": p01, "p10": p10,
                     "readout_total": p01 + p10,
                     "T1_us": _prop(props, qi, "T1"),
                     "T2_us": _prop(props, qi, "T2"),
                     "sx_error": sx})
    return {"backend": backend.name,
            "last_update_date": str(props.last_update_date),
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "qubits": rows}


def c_key(row):
    tie = -(min(row["T1_us"] or math.inf, row["T2_us"] or math.inf))
    return (row["readout_total"], tie)


def rank_rows(rows):
    return sorted(rows, key=c_key)


def stratified_pick(ranked):
    """Deterministic: best + nearest-rank p25/p50/p75/p95 + q37 anchor."""
    n = len(ranked)
    idxs = [0]
    for f in (0.25, 0.50, 0.75, 0.95):
        idxs.append(min(n - 1, math.ceil(f * (n - 1))))
    picked = [ranked[i] for i in idxs]
    qs = [r["q"] for r in picked]
    if 37 not in qs:
        row37 = next(r for r in ranked if r["q"] == 37)
        picked.append(row37)
    return picked


# --------------------------------------------------------------- overhead
def overhead_bench(backend, snapshot_rows):
    """H3.3: selector latency and transpile overhead, absolute ms."""
    order = rank_rows(snapshot_rows)
    reps = 200
    t0 = time.perf_counter()
    for _ in range(reps):
        best = min(snapshot_rows, key=c_key)
    dt_sel_ms = (time.perf_counter() - t0) * 1000.0 / reps

    from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
    bits = [1, 0, 1, 1]
    qc = build_circuit(rotation_angle(0.5))  # single-qubit encoding cell
    times_pinned, times_free = [], []
    for _ in range(3):
        pm_pin = generate_preset_pass_manager(
            backend=backend, optimization_level=1, seed_transpiler=SEED,
            initial_layout=[best["q"]])
        t0 = time.perf_counter()
        pm_pin.run(qc)
        times_pinned.append((time.perf_counter() - t0) * 1000.0)
        pm_free = generate_preset_pass_manager(
            backend=backend, optimization_level=1, seed_transpiler=SEED)
        t0 = time.perf_counter()
        pm_free.run(qc)
        times_free.append((time.perf_counter() - t0) * 1000.0)

    # multi-qubit aware-layout probe (greedy connected subset by C)
    t0 = time.perf_counter()
    subset = greedy_connected(best["q"], k=3, ranked=order, edges=coupling_edges(backend))
    dt_route3_ms = (time.perf_counter() - t0) * 1000.0
    return {
        "selector_argmin_ms": round(dt_sel_ms, 4),
        "transpile_pinned_ms_median": round(sorted(times_pinned)[1], 1),
        "transpile_free_ms_median": round(sorted(times_free)[1], 1),
        "aware_layout_3q_ms": round(dt_route3_ms, 3),
        "aware_layout_3q_choice": [r["q"] for r in subset],
    }


def coupling_edges(backend):
    try:
        return {(int(a), int(b)) for a, b in backend.coupling_map.get_edges()}
    except Exception:
        return set()


def greedy_connected(start, k, ranked, edges):
    """Pick k qubits: BFS from `start` over coupling map, always expanding
    through the neighbour with best C(q)."""
    score = {r["q"]: c_key(r) for r in ranked}
    chosen = [start]
    seen = {start}
    frontier = [start]
    while len(chosen) < k and frontier:
        nxt_list = []
        for u in frontier:
            for v in [t for s, t in edges if s == u] + [s for s, t in edges if t == u]:
                if v not in seen:
                    nxt_list.append(v)
        if not nxt_list:
            break
        v_best = min(set(nxt_list), key=lambda v: score.get(v, (math.inf, 0)))
        chosen.append(v_best)
        seen.add(v_best)
        frontier = [v_best]
    return [next(r for r in ranked if r["q"] == q) for q in chosen]


# --------------------------------------------------------------- local
def part_local() -> int:
    from qiskit_ibm_runtime import QiskitRuntimeService
    service = QiskitRuntimeService()
    backend = service.backend(BACKEND)
    snap = fetch_table(backend)
    RES.mkdir(exist_ok=True)
    (RES / "calib_full_e08.json").write_text(json.dumps(snap, indent=2))

    ranked = rank_rows(snap["qubits"])
    n = len(ranked)
    rank_of = {r["q"]: i + 1 for i, r in enumerate(ranked)}

    print("== C(q) ranking ({}) snapshot {} ==".format(
        n, snap["last_update_date"]))
    print("best : q{:>3} readout={:.5f} T1={:.0f}us T2={:.0f}us".format(
        ranked[0]["q"], ranked[0]["readout_total"],
        ranked[0]["T1_us"] or -1, ranked[0]["T2_us"] or -1))
    print("worst: q{:>3} readout={:.5f}".format(
        ranked[-1]["q"], ranked[-1]["readout_total"]))
    med = sorted(r["readout_total"] for r in ranked)[n // 2]
    print("device median readout_total = {:.5f}".format(med))

    print("\nanchor check vs E-05 (recorded 2026-08-22 snapshot):")
    for q, old in ANCHOR_E05.items():
        r = next(x for x in ranked if x["q"] == q)
        drift = (r["readout_total"] - old) / old * 100.0
        print("  q{:>3}: now={:.6f} e05={:.6f} (drift {:+.1f}%) rank {}/{}".format(
            q, r["readout_total"], old, drift, rank_of[q], n))

    picks = stratified_pick(ranked)
    print("\nstratified validation set:")
    for r in picks:
        pct = 100.0 * (rank_of[r["q"]] - 1) / (n - 1)
        print("  q{:>3}  rank {:>3}/{n}  pct {:>5.1f}%  readout {:.5f}".format(
            r["q"], rank_of[r["q"]], pct, r["readout_total"], n=n))

    ov = overhead_bench(backend, snap["qubits"])
    print("\noverhead microbench: {}".format(ov))

    (RES / "router_local.json").write_text(json.dumps({
        "snapshot_file": "calib_full_e08.json",
        "last_update_date": snap["last_update_date"],
        "n_usable": n,
        "median_readout_total": med,
        "anchors": {str(q): {"now": next(r["readout_total"] for r in ranked if r["q"] == q),
                             "e05": old, "rank": rank_of[q]}
                    for q, old in ANCHOR_E05.items()},
        "selected": [{**r, "rank": rank_of[r["q"]],
                      "percentile": round(100.0 * (rank_of[r["q"]] - 1) / (n - 1), 1)}
                     for r in picks],
        "overhead": ov,
    }, indent=2))
    print("\nsaved -> analysis/results/{calib_full_e08,router_local}.json")
    return 0


# --------------------------------------------------------------- qpu
def part_qpu() -> int:
    local = json.loads((RES / "router_local.json").read_text())
    targets = [row["q"] for row in local["selected"]]
    SWEEP_DIR.mkdir(parents=True, exist_ok=True)

    from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
    from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2
    service = QiskitRuntimeService()
    backend = service.backend(BACKEND)
    snap = json.loads((RES / "calib_full_e08.json").read_text())
    cal_of = {r["q"]: r for r in snap["qubits"]}

    for qi in targets:
        dest = SWEEP_DIR / "router_sweep_q{}.json".format(qi)
        if dest.exists():
            print("q{}: exists, skip".format(qi))
            continue
        pm = generate_preset_pass_manager(
            backend=backend, optimization_level=1, seed_transpiler=SEED,
            initial_layout=[qi])
        circuits = [pm.run(build_circuit(rotation_angle(w))) for w in WEIGHTS]
        sampler = SamplerV2(mode=backend)
        job = sampler.run([(qc, None, SHOTS) for qc in circuits])
        print("q{}: job {} submitted (19 circuits x {})...".format(qi, job.job_id(), SHOTS))
        result = job.result(timeout=7200)
        rows = []
        for i, w in enumerate(WEIGHTS):
            counts = result[i].data.c.get_counts()
            p1 = counts.get("1", 0) / SHOTS
            rows.append({"w": w, "p1": p1, "shots": SHOTS,
                         "z_theory": 1.0 - 2.0 * w, "z_emp": 1.0 - 2.0 * p1,
                         "dev": abs((1.0 - 2.0 * p1) - (1.0 - 2.0 * w))})
        dest.write_text(json.dumps({
            "q": qi, "backend": BACKEND, "job_id": job.job_id(),
            "shots": SHOTS, "seed_transpiler": SEED, "weights": WEIGHTS,
            "variant": "bare", "pinned": True,
            "placed_qubit": circuits[0].layout.initial_index_layout(filter_ancillas=True)[0],
            "calibration": cal_of[qi],
            "rows": rows,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }, indent=2))
        print("q{}: saved, max_dev={:.4f}".format(qi, max(r["dev"] for r in rows)))
    return 0


# --------------------------------------------------------------- analyze
def affine_fit(rows):
    """p_obs = b + a*w, least squares."""
    ws = [r["w"] for r in rows]
    ps = [r["p1"] for r in rows]
    n = len(ws)
    mw, mp = sum(ws) / n, sum(ps) / n
    sxx = sum((w - mw) ** 2 for w in ws)
    swp = sum((w - mw) * (p - mp) for w, p in zip(ws, ps))
    a = swp / sxx
    b = mp - a * mw
    return a, b


def spearman_exact(xs, ys):
    """Exact permutation Spearman rho + two-sided p (small n)."""
    n = len(xs)
    rx = {v: i for i, v in enumerate(sorted(range(n), key=lambda i: xs[i]))}
    ry = {v: i for i, v in enumerate(sorted(range(n), key=lambda i: ys[i]))}
    dx = [rx[i] for i in range(n)]
    dy = [ry[i] for i in range(n)]
    obs_rho = _rho(dx, dy)
    count, total = 0, 0
    for perm in permutations(dy):
        total += 1
        if abs(_rho(dx, perm) - obs_rho) > 1e-9 or abs(_rho(dx, perm) - obs_rho) < 1e-12:
            pass
    # exact two-sided p by enumeration
    ge = sum(1 for perm in permutations(dy) if abs(_rho(dx, perm)) >= abs(obs_rho) - 1e-12)
    return obs_rho, ge / total


def _rho(x, y):
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    num = sum((a - mx) * (b - my) for a, b in zip(x, y))
    den = math.sqrt(sum((a - mx) ** 2 for a in x) * sum((b - my) ** 2 for b in y))
    return num / den if den else float("nan")


def part_analyze() -> int:
    local = json.loads((RES / "router_local.json").read_text())
    sel = {row["q"]: row for row in local["selected"]}
    cells = []
    for path in sorted(SWEEP_DIR.glob("router_sweep_q*.json")):
        d = json.loads(path.read_text())
        qi = d["q"]
        md = max(r["dev"] for r in d["rows"])
        pr = sum(1 for r in d["rows"] if r["dev"] <= TOL) / len(d["rows"])
        a, b = affine_fit(d["rows"])
        cal = d["calibration"]
        cells.append({"q": qi, "rank": sel[qi]["rank"],
                      "percentile": sel[qi]["percentile"],
                      "readout_total": cal["readout_total"],
                      "max_dev": round(md, 4), "pass_rate": round(pr, 3),
                      "affine_a": round(a, 4), "affine_b": round(b, 4),
                      "job_id": d["job_id"]})
    if not cells:
        print("no sweep data yet -- run --part qpu first")
        return 1
    cells.sort(key=lambda c: c["rank"])
    print("== E-08 measured cells (sorted by C(q) rank) ==")
    print("q    rank  pct    readout   max_dev pass  a      b")
    for c in cells:
        print("q{:<3} {:>4} {:>5.1f}  {:.5f}  {:.4f}  {:.2f}  {:+.3f} {:+.3f}".format(
            c["q"], c["rank"], c["percentile"], c["readout_total"],
            c["max_dev"], c["pass_rate"], c["affine_a"], c["affine_b"]))

    rho, p = spearman_exact([c["readout_total"] for c in cells],
                            [c["max_dev"] for c in cells])
    top = cells[0]
    bottom = cells[-1]
    upper = [c for c in cells if c["percentile"] <= 50.0]
    h32 = (top["max_dev"] <= TOL) and (bottom["max_dev"] > TOL)
    h31 = all(c["pass_rate"] >= 0.90 for c in upper) if upper else False
    ov = local["overhead"]
    h33 = ov["selector_argmin_ms"] < 1.0 and ov["transpile_pinned_ms_median"] < 500.0
    verdicts = {
        "H3.2_score_validity": {"pass": h32,
                                "detail": "top-1 q{} max_dev={} vs bottom q{} {}".format(
                                    top["q"], top["max_dev"], bottom["q"], bottom["max_dev"])},
        "H3.1_upper_half_ge_90pct": {"pass": h31,
                                     "detail": ["q{}:{:.0%}".format(c["q"], c["pass_rate"])
                                                for c in upper]},
        "H3.3_overhead_ms": {"pass": h33, "overhead": ov},
        "spearman_C_vs_maxdev": {"rho": round(rho, 3), "p_exact": round(p, 4)},
    }
    print("\nverdicts: {}".format(json.dumps(verdicts, indent=2)))

    (RES / "router_analysis.json").write_text(json.dumps(
        {"cells": cells, "verdicts": verdicts}, indent=2))
    print("saved -> analysis/results/router_analysis.json")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", choices=["local", "qpu", "analyze"], required=True)
    args = ap.parse_args()
    return {"local": part_local, "qpu": part_qpu, "analyze": part_analyze}[args.part]()


if __name__ == "__main__":
    raise SystemExit(main())
