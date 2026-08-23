"""E-09 (RQ5) -- End-to-end chain composition on real hardware.

Full chain: NL intent -> mock LLM (q=0.7, f_r=0.1) -> UniMind orchestration
(validation / self-healing / rule-based fallback per arm) -> Unibit fold ->
hardware-aware placement -> ibm_marrakesh -> result.

Arms (independent mock streams, identical task sets):
  FULL    = S3X semantics (validation+heal+S3X fallback) + aware placement
            (circuits pinned to the best-C(q) connected qubit chain of the
             frozen E-08 snapshot -- the SAME calibration as every other E-x)
  ABLATED = S1 semantics (validation-only, no heal, no fallback) + default
            free placement (v1.7 behaviour)

Task set: 9 intent classes x 6 reps (seeds 42/43 x 3 interleaved reps) = 54
tasks/arm; quantum classes {angle, bell, ghz} additionally execute on the
QPU. All quantum PUBs of an arm are submitted as ONE batched job (4096
shots). Mock-vs-real boundary: the LLM stage is simulated (documented);
sandbox execution, transpilation, placement, and QPU submission are real.

Boundary note: the hardware step is driven by the task SPECIFICATION (bits /
state prep) rather than by parsing generated sandbox code; the orchestration
layer decides WHETHER the task reaches hardware (first-pass / healed /
fallback / failed). This composes the measured software-path probabilities
(A-01 model) with real hardware fidelity.

Stages (quota-safe):
  submit  build orchestration rows + PUBs deterministically, submit one
          batched job per arm, persist EVERYTHING needed for later scoring
          (job_id included) to data/e2e/e2e_<arm>_pending.json
  collect fetch job results by id, score fidelity, write e2e_<arm>.json,
          print charter verdicts H5.1/H5.2/H5.3
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "unimind-dev"))

from mock_llm import InstrumentedMock, generate_tasks, run_one_config, wilson  # noqa: E402
from ablation_study import build_link  # noqa: E402
from hw_router import rank_rows, greedy_connected, coupling_edges  # noqa: E402

RES = Path(__file__).resolve().parent / "results"
DATA = Path(__file__).resolve().parent.parent / "data" / "e2e"
SNAPSHOT = RES / "calib_full_e08.json"
SHOTS = 4096
SEED_TRANSPILE = 42
TOL = 0.05
QUANTUM_KINDS = ("angle", "bell", "ghz")
REPS_PER_SEED = 3
SEEDS = (42, 43)
MOCK_SEED = 20260823


def rotation_angle(w):
    return 2.0 * math.asin(math.sqrt(w))


def window_mean(bits, i, delta=2):
    lo, hi = max(0, i - delta), min(len(bits) - 1, i + delta)
    seg = bits[lo:hi + 1]
    return sum(seg) / len(seg)


def circuit_for(kind, intent):
    """Build the hardware circuit demanded by an NL intent (pure-Ry branch,
    paper Eq./Algorithm semantics; see docs/unibit_math.md P3)."""
    from qiskit import QuantumCircuit
    if kind == "angle":
        m = re.search(r"bits (\[.*?\])", intent)
        bits = [int(b) for b in m.group(1).strip("[]").split(",")]
        n = len(bits)
        qc = QuantumCircuit(n, n)
        for i, b in enumerate(bits):
            qc.ry(rotation_angle(window_mean(bits, i)), i)
        qc.measure(range(n), range(n))
        return qc, {"kind": "angle", "bits": bits}
    if kind == "bell":
        qc = QuantumCircuit(2, 2)
        qc.h(0)
        qc.cx(0, 1)
        qc.measure([0, 1], [0, 1])
        return qc, {"kind": "bell"}
    if kind == "ghz":
        qc = QuantumCircuit(3, 3)
        qc.h(0)
        qc.cx(0, 1)
        qc.cx(1, 2)
        qc.measure([0, 1, 2], [0, 1, 2])
        return qc, {"kind": "ghz"}
    raise ValueError(kind)


SUCCESS_PATHS = {"first_pass", "healed", "fallback_ok"}

# job submitted in a previous session whose pending file was lost
# (shell timeout while blocked on quota); metadata is deterministically
# reproducible from the same snapshot + seeds + transpiler seed
KNOWN_JOB_IDS = {"full": "da5c8kuaa69c739kmr40"}


# ------------------------------------------------------------------ build
def build_stage(arm: str, ranked_rows, edges, backend) -> dict:
    """Deterministic orchestration + transpilation. Returns pending dict."""
    tasks = []
    for seed in SEEDS:
        tasks.extend(generate_tasks(9 * REPS_PER_SEED, 0, seed))
    for i, t in enumerate(tasks):
        t["id"] = "t{:02d}".format(i)

    tag = "S3X" if arm == "full" else "S1"
    mock = InstrumentedMock(0.7, 0.1, MOCK_SEED)
    link = build_link(tag)
    intent_by_id = {t["id"]: t["intent"] for t in tasks}

    t0 = time.perf_counter()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rows = run_one_config(link, mock, tasks)
    orch_ms = (time.perf_counter() - t0) * 1000.0

    from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
    pubs, pub_meta, tp_ms = [], [], []
    for row in rows:
        if row["class"] != "valid" or row["kind"] not in QUANTUM_KINDS:
            continue
        if row["path"] not in SUCCESS_PATHS:
            continue
        qc, spec = circuit_for(row["kind"], intent_by_id[row["id"]])
        ts = time.perf_counter()
        if arm == "full":
            k = qc.num_qubits
            chain = greedy_connected(ranked_rows[0]["q"], k, ranked_rows, edges)
            pm = generate_preset_pass_manager(
                backend=backend, optimization_level=1,
                seed_transpiler=SEED_TRANSPILE,
                initial_layout=[r["q"] for r in chain])
        else:
            pm = generate_preset_pass_manager(
                backend=backend, optimization_level=1,
                seed_transpiler=SEED_TRANSPILE)
        tc = pm.run(qc)
        tp_ms.append((time.perf_counter() - ts) * 1000.0)
        try:
            placed = tc.layout.initial_index_layout(filter_ancillas=True)
        except Exception:
            placed = []
        pubs.append(tc)
        pub_meta.append({"task": row["id"], "kind": row["kind"],
                         "orch_path": row["path"], "spec": spec,
                         "placed_qubits": list(placed),
                         "n_qubits": qc.num_qubits})

    out_rows = [{k: v for k, v in r.items() if k != "gt"} for r in rows]
    pending = {"arm": arm, "orch_tag": tag,
               "orch_ms": round(orch_ms, 1),
               "transpile_ms_median": round(sorted(tp_ms)[len(tp_ms) // 2], 1) if tp_ms else None,
               "n_pubs": len(pubs),
               "rows": out_rows, "pub_meta": pub_meta}
    return pending, pubs


def stage_submit() -> int:
    snap = json.loads(SNAPSHOT.read_text())
    ranked = rank_rows(snap["qubits"])
    DATA.mkdir(parents=True, exist_ok=True)

    from qiskit_ibm_runtime import QiskitRuntimeService
    service = QiskitRuntimeService()
    backend = service.backend("ibm_marrakesh")
    edges = coupling_edges(backend)

    for arm in ("full", "ablated"):
        dest = DATA / "e2e_{}_pending.json".format(arm)
        if dest.exists():
            pending = json.loads(dest.read_text())
            if pending.get("job_id"):
                print("[{}] already submitted: {}".format(arm, pending["job_id"]))
                continue
        pending, circuits = build_stage(arm, ranked, edges, backend)
        if arm in KNOWN_JOB_IDS:
            pending["job_id"] = KNOWN_JOB_IDS[arm]
            print("[{}] attached known job {} (no resubmission)".format(
                arm, pending["job_id"]))
        else:
            from qiskit_ibm_runtime import SamplerV2
            sampler = SamplerV2(mode=backend)
            job = sampler.run([(qc, None, SHOTS) for qc in circuits])
            pending["job_id"] = job.job_id()
            print("[{}] submitted {} PUBs -> {} (queued)".format(
                arm, pending["n_pubs"], pending["job_id"]))
        pending["shots"] = SHOTS
        pending["submitted_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        dest.write_text(json.dumps(pending, indent=2))
    return 0


# ---------------------------------------------------------------- collect
def stage_collect() -> int:
    from qiskit_ibm_runtime import QiskitRuntimeService
    service = QiskitRuntimeService()
    finals = {}
    for arm in ("full", "ablated"):
        pend_p = DATA / "e2e_{}_pending.json".format(arm)
        final_p = DATA / "e2e_{}.json".format(arm)
        if final_p.exists():
            finals[arm] = json.loads(final_p.read_text())
            continue
        if not pend_p.exists():
            print("[{}] no pending data -- run --stage submit first".format(arm))
            continue
        pending = json.loads(pend_p.read_text())
        jid = pending.get("job_id")
        if not jid:
            print("[{}] pending has no job_id yet".format(arm))
            continue
        job = service.job(jid)
        st = job.status()
        if str(st) != "DONE":
            print("[{}] job {} status: {}".format(arm, jid, st))
            continue
        result = job.result()

        hw = []
        for mi, meta in enumerate(pending["pub_meta"]):
            counts = result[mi].data.c.get_counts()
            total = sum(counts.values()) or 1
            entry = dict(meta)
            if meta["kind"] == "angle":
                bits = meta["spec"]["bits"]
                n = len(bits)
                devs = []
                for i in range(n):
                    p1 = sum(c for c, k in counts.items()
                             if len(k.replace(" ", "")) == n
                             and k.replace(" ", "")[::-1][i] == "1") / total
                    w = window_mean(bits, i)
                    devs.append(abs((1.0 - 2.0 * p1) - (1.0 - 2.0 * w)))
                entry.update({"per_bit_dev": [round(d, 4) for d in devs],
                              "weights_ok": int(sum(d <= TOL for d in devs)),
                              "n_weights": n,
                              "hw_pass": all(d <= TOL for d in devs)})
            else:
                ks = [k.replace(" ", "") for k in counts]
                same = sum(c for c, k in zip(counts.values(), ks)
                           if len(set(k)) == 1) / total
                entry.update({"parity_same": round(same, 4),
                              "parity_dev": round(abs(same - 1.0), 4),
                              "hw_pass": None})
            hw.append(entry)

        final = dict(pending)
        final["hardware"] = hw
        final.pop("qasm_list", None)
        final_p.write_text(json.dumps(final, indent=2))
        finals[arm] = final
        print("[{}] collected job {}".format(arm, jid))

    if "full" in finals and "ablated" in finals:
        verdicts(finals["full"], finals["ablated"])
    return 0


def e2e_count(res):
    hw_by_task = {h["task"]: h for h in res.get("hardware", [])}
    n = len(res["rows"])
    e2e = sum(1 for r in res["rows"]
              if r["path"] in SUCCESS_PATHS
              and (r["kind"] not in QUANTUM_KINDS
                   or hw_by_task.get(r["id"], {}).get("hw_pass") is True))
    return e2e, n


def verdicts(f, a):
    ef, nf = e2e_count(f)
    ea, na = e2e_count(a)
    lo_f, hi_f = wilson(ef, nf)
    lo_a, hi_a = wilson(ea, na)
    aw = [h for h in f.get("hardware", []) if h["kind"] == "angle"]
    w_ok = sum(h["weights_ok"] for h in aw)
    w_n = sum(h["n_weights"] for h in aw)
    par = [(h["kind"], h["parity_dev"]) for h in f.get("hardware", [])
           if h["kind"] in ("bell", "ghz")]

    def paths(res):
        d = {}
        for r in res["rows"]:
            d[r["path"]] = d.get(r["path"], 0) + 1
        return d

    print("\n== E-09 verdict ==")
    print("H5.1 integration: {} NL tasks/arm through the full chain; "
          "jobs {} / {}".format(nf, f.get("job_id"), a.get("job_id")))
    print("paths full   : {}".format(paths(f)))
    print("paths ablated: {}".format(paths(a)))
    print("H5.2 gain: P_E2E full {:.1f}% ci({:.1f},{:.1f}) vs ablated "
          "{:.1f}% ci({:.1f},{:.1f}){}".format(
              100 * ef / nf, 100 * lo_f, 100 * hi_f,
              100 * ea / na, 100 * lo_a, 100 * hi_a,
              "  [CI-separated]" if lo_f > hi_a else "  [CIs overlap]"))
    print("H5.3 fidelity: angle weights within tolerance {}/{} = {:.0%}".format(
        w_ok, w_n, w_ok / w_n if w_n else float("nan")))
    print("parity devs (full): {}".format(par))
    summary = {"P_E2E_full_pct": round(100 * ef / nf, 1),
               "P_E2E_full_ci": [round(100 * lo_f, 1), round(100 * hi_f, 1)],
               "P_E2E_ablated_pct": round(100 * ea / na, 1),
               "P_E2E_ablated_ci": [round(100 * lo_a, 1), round(100 * hi_a, 1)],
               "angle_weights_ok": w_ok, "angle_weights_total": w_n,
               "job_full": f.get("job_id"), "job_ablated": a.get("job_id"),
               "orch_paths_full": paths(f), "orch_paths_ablated": paths(a)}
    (DATA / "e2e_summary.json").write_text(json.dumps(summary, indent=2))
    print("saved -> data/e2e/e2e_summary.json")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["submit", "collect"], required=True)
    args = ap.parse_args()
    return {"submit": stage_submit, "collect": stage_collect}[args.stage]()


if __name__ == "__main__":
    raise SystemExit(main())
