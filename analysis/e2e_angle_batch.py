"""E-09b: adequate-sample E2E placement batch (2026-08-31).

Pre-registered protocol (protocol.md E-09): same task stream, same frozen
snapshot (calib_2026-08-29.json, the E-08 capture behind Table tab:routing),
same placement policy, but with angle PUB sample raised from 6 to 30 per arm
so the hardware placement comparison has usable power.

Arms (one batched job each, 4096 shots/PUB):
  FULL    = angle circuit pinned by greedy connected chain grown from the
            best-C(q) qubit of the frozen snapshot (calib_2026-08-29)
  ABLATED = same circuit, default free transpiler placement (v1.7 behaviour)

Fidelity: per-bit |<Z> - (1-2*w_t)| <= TOL=0.05 (same as E-09).

Outputs (quota-safe persist for later scoring):
  data/e2e/e2e_angle_<arm>_pending.json  (rows, pub_meta, job_id, submitted_at)
  collect via --stage collect, writes e2e_angle_<arm>.json + a summary.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "unimind-dev"))
from e2e_chain import (SHOTS, TOL, window_mean, rotation_angle,
                       circuit_for, greedy_connected, coupling_edges)  # noqa: E402
from hw_router import rank_rows, fetch_table, c_key  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "analysis" / "results"
DATA = ROOT / "data" / "e2e"
# frozen E-08 snapshot (git HEAD) -- SAME calibration as Section routing.
FROZEN = ROOT / "data" / "drift" / "calib_2026-08-29.json"
N_ANGLE = 30         # angle circuits per arm (6 in the original E-09)
N_BITS = 6           # angle encoding width (level of the original stream)
SEED_ANGLE = 20260831
BACKEND = "ibm_marrakesh"


def angle_specs(n: int, nbits: int, seed: int):
    """Deterministic suite of n-bit angle specs (window_mean over nbits).

    Each spec is {"kind": "angle", "bits": [...]}; seeded RNG guards against
    accidental drift while keeping full traceability in the pending JSON.
    """
    rng = random.Random(seed)
    specs = []
    seen = set()
    while len(specs) < n:
        bits = [rng.randint(0, 1) for _ in range(nbits)]
        key = tuple(bits)
        if key in seen:
            continue
        seen.add(key)
        specs.append({"kind": "angle", "bits": bits})
    return specs


def build(specs, ranked, edges, backend):
    from qiskit import QuantumCircuit
    pub_meta, qcs = [], []
    for spec in specs:
        bits = spec["bits"]
        n = len(bits)
        qc = QuantumCircuit(n, n)
        for i, b in enumerate(bits):
            qc.ry(rotation_angle(window_mean(bits, i)), i)
        qc.measure(range(n), range(n))
        chain = greedy_connected(ranked[0]["q"], n, ranked, edges)
        initial_layout = [r["q"] for r in chain]
        pm = generate_preset_pass_manager(
            backend=backend, optimization_level=1,
            seed_transpiler=42, initial_layout=initial_layout)
        tc = pm.run(qc)
        placed = tc.layout.initial_index_layout(filter_ancillas=True)
        pub_meta.append({"spec": spec, "placed_qubits": list(placed),
                         "n_qubits": n})
        qcs.append(tc)
    return pub_meta, qcs


def chain_grow(start, k, ranked, edges):
    """k connected qubits by Prim-style expansion: among all neighbours of the
    chosen set, always add the lowest-C one. Guarantees growth until the
    full device component is exhausted (unlike greedy_connected's linear
    walk, which can stall on the heavy-hex boundary for large k)."""
    score = {r["q"]: c_key(r) for r in ranked}
    chosen = [start]
    chosen_set = {start}
    while len(chosen) < k:
        cand = []
        for u in chosen_set:
            for v in ([t for s, t in edges if s == u]
                      + [s for s, t in edges if t == u]):
                if v not in chosen_set:
                    cand.append(v)
        if not cand:
            break
        v_best = min(set(cand), key=lambda v: score.get(v, (math.inf, 0)))
        chosen.append(v_best)
        chosen_set.add(v_best)
    return [next(r for r in ranked if r["q"] == q) for q in chosen]


def generate_preset_pass_manager(*args, **kw):
    from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager as g
    return g(*args, **kw)


def stage_submit():
    from qiskit_ibm_runtime import QiskitRuntimeService
    service = QiskitRuntimeService()
    backend = service.backend(BACKEND)

    if args.refresh:
        snap = fetch_table(backend)
        snap_path = DATA.parent / "drift" / "calib_2026-08-31.json"
        snap_path.parent.mkdir(parents=True, exist_ok=True)
        snap_path.write_text(json.dumps(snap, indent=2))
        print("refreshed snapshot -> {} (latest update {})".format(
            snap_path, snap.get("last_update_date")))
    else:
        snap = json.loads(FROZEN.read_text())
        snap_path = FROZEN
    ranked = rank_rows(snap["qubits"])
    DATA.mkdir(parents=True, exist_ok=True)

    edges = coupling_edges(backend)

    specs_full = angle_specs(N_ANGLE, N_BITS, SEED_ANGLE)
    # ablated uses the same suite but free placement
    for arm in ("full", "ablated"):
        dest = DATA / "e2e_angle_{}_pending.json".format(
            arm if not args.refresh else "{}_refresh".format(arm))
        if dest.exists():
            j = json.loads(dest.read_text())
            if j.get("job_id") and not args.force:
                print("[{}] already submitted: {} -- skip (use --force)".format(arm, j["job_id"]))
                continue

        if arm == "full":
            pub_meta, qcs = build(specs_full, ranked, edges, backend)
        else:
            from qiskit import QuantumCircuit
            pub_meta, qcs = [], []
            for spec in specs_full:
                bits = spec["bits"]; n = len(bits)
                qc = QuantumCircuit(n, n)
                for i, b in enumerate(bits):
                    qc.ry(rotation_angle(window_mean(bits, i)), i)
                qc.measure(range(n), range(n))
                pm = generate_preset_pass_manager(
                    backend=backend, optimization_level=1, seed_transpiler=42)
                tc = pm.run(qc)
                placed = tc.layout.initial_index_layout(filter_ancillas=True)
                pub_meta.append({"spec": spec, "placed_qubits": list(placed),
                                 "n_qubits": n})
                qcs.append(tc)

        from qiskit_ibm_runtime import SamplerV2
        sampler = SamplerV2(mode=backend)
        job = sampler.run([(qc, None, SHOTS) for qc in qcs])
        pending = {"arm": arm, "suite_seed": SEED_ANGLE, "n": N_ANGLE,
                   "nbits": N_BITS, "snapshot": snap_path.name,
                   "snapshot_fetched_at": snap.get("fetched_at"),
                   "snapshot_last_update": snap.get("last_update_date"),
                   "pub_meta": pub_meta, "job_id": job.job_id(),
                   "shots": SHOTS,
                   "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        dest.write_text(json.dumps(pending, indent=2))
        print("[{}] submitted {} angle PUBs -> {}".format(arm, len(qcs), job.job_id()))
    return 0


def score(entry, counts, total):
    kind = "angle"
    spec = entry["spec"]; bits = spec["bits"]; n = len(bits)
    devs = []
    for i in range(n):
        p1 = sum(c for k, c in counts.items()
                 if len(k.replace(" ", "")) == n
                 and k.replace(" ", "")[::-1][i] == "1") / total
        w = window_mean(bits, i)
        devs.append(abs((1.0 - 2.0 * p1) - (1.0 - 2.0 * w)))
    return {"per_bit_dev": [round(d, 4) for d in devs],
            "weights_ok": int(sum(d <= TOL for d in devs)),
            "n_weights": n,
            "hw_pass": all(d <= TOL for d in devs),
            "max_dev": round(max(devs), 4)}


def stage_collect():
    from qiskit_ibm_runtime import QiskitRuntimeService
    service = QiskitRuntimeService()
    results = {}
    for arm in ("full", "ablated"):
        tag = arm if not args.refresh else "{}_refresh".format(arm)
        pend_p = DATA / "e2e_angle_{}_pending.json".format(tag)
        final_p = DATA / "e2e_angle_{}.json".format(tag)
        if final_p.exists() and not args.force:
            results[arm] = json.loads(final_p.read_text())
            continue
        pending = json.loads(pend_p.read_text())
        job = service.job(pending["job_id"])
        if str(job.status()) != "DONE":
            print("[{}] status {}".format(arm, job.status()))
            continue
        result = job.result()
        hw = []
        for mi, meta in enumerate(pending["pub_meta"]):
            if mi >= len(result):
                break
            counts = result[mi].data.c.get_counts()
            total = sum(counts.values()) or 1
            entry = dict(meta); entry.update(score(meta, counts, total))
            hw.append(entry)
        final = dict(pending); final["hardware"] = hw
        final.pop("qasm_list", None)
        final_p.write_text(json.dumps(final, indent=2))
        results[arm] = final
        print("[{}] collected {} circuits".format(arm, len(hw)))

    if "full" in results and "ablated" in results:
        for arm in ("full", "ablated"):
            r = results[arm]
            pw = sum(1 for h in r["hardware"] if h["hw_pass"])
            tot = len(r["hardware"])
            print("  {} angle pass {}/{} = {:.1f}%".format(arm, pw, tot, 100*pw/tot))
            nz = sum(1 for h in r["hardware"] if h["max_dev"] >= TOL)
            print("    circuits with a bit > {}: {}".format(TOL, nz))
    return 0


def main():
    global args
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["submit", "collect"], required=True)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--refresh", action="store_true",
                    help="fetch a fresh calibration snapshot for pins (default: frozen 08-29)")
    args = ap.parse_args()
    return {"submit": stage_submit, "collect": stage_collect}[args.stage]()


if __name__ == "__main__":
    raise SystemExit(main())