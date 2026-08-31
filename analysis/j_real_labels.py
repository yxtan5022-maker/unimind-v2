"""J(G) real-QPU labels for circuit sizes k in {9..18} (2026-08-31).

Purpose: replace the est-2q simulation proxy with real hardware y for the
unmeasured-big sizes of the 7-dim J(G) dataset, so the decision-model
(Stage-3) claims are not proxy-only for k>8.

Protocol (pre-registered, mirrors Stage-1 real sweep):
  - angle-encoding circuits (standard window-mean Ry encoding, same as E-09)
    of width k, placed by greedy connected chain grown from the best-C(q)
    qubit of the frozen 08-29 snapshot (SAME calibration as Sections routing).
  - y_real(k, pattern) = max per-bit |<Z> - (1-2 w_i)| over 4096 shots.
  - suite: k in {9,10,11,12,14,16,18} x 2 seeded bit patterns = 14 PUBs,
    one batched job (4096 shots/PUB), quota-lean.
Persist for later scoring: data/jgpu/j_real_pending.json (+ collected 
data/jgpu/j_real.json with per-bit dev and max_dev).
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "unimind-dev"))
from e2e_chain import SHOTS, TOL, window_mean, rotation_angle, coupling_edges  # noqa: E402
from e2e_angle_batch import chain_grow  # noqa: E402
from hw_router import rank_rows  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "jgpu"
FROZEN = ROOT / "data" / "drift" / "calib_2026-08-29.json"
KS = (9, 10, 11, 12, 14, 16, 18)
PATTERNS_PER_K = 2
SEED = 20260831
BACKEND = "ibm_marrakesh"


def pattern(k: int, seed: int):
    rng = random.Random(seed)
    return [rng.randint(0, 1) for _ in range(k)]


def stage_submit():
    from qiskit_ibm_runtime import QiskitRuntimeService
    service = QiskitRuntimeService()
    backend = service.backend(BACKEND)

    if args.refresh:
        from hw_router import fetch_table
        snap = fetch_table(backend)
        snap_path = DATA.parent / "drift" / "calib_2026-08-31.json"
        snap_path.parent.mkdir(parents=True, exist_ok=True)
        snap_path.write_text(json.dumps(snap, indent=2))
        print("refreshed snapshot -> {}".format(snap_path))
    else:
        snap = json.loads(FROZEN.read_text())
        snap_path = FROZEN
    ranked = rank_rows(snap["qubits"])
    DATA.mkdir(parents=True, exist_ok=True)
    tag = "j_real" if not args.refresh else "j_real_refresh"
    dest = DATA / "{}_pending.json".format(tag)
    if dest.exists():
        j = json.loads(dest.read_text())
        if j.get("job_id") and not args.force:
            print("already submitted: {} -- skip (use --force)".format(j["job_id"]))
            return 0

    from qiskit import QuantumCircuit
    from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
    from qiskit_ibm_runtime import SamplerV2
    edges = coupling_edges(backend)

    specs, qcs, pub_meta = [], [], []
    idx = 0
    for k in KS:
        for p in range(PATTERNS_PER_K):
            bits = pattern(k, SEED + idx)
            idx += 1
            n = len(bits)
            qc = QuantumCircuit(n, n)
            for i, b in enumerate(bits):
                qc.ry(rotation_angle(window_mean(bits, i)), i)
            qc.measure(range(n), range(n))
            chain = chain_grow(ranked[0]["q"], n, ranked, edges)
            pm = generate_preset_pass_manager(
                backend=backend, optimization_level=1, seed_transpiler=42,
                initial_layout=[r["q"] for r in chain])
            tc = pm.run(qc)
            placed = tc.layout.initial_index_layout(filter_ancillas=True)
            specs.append({"kind": "angle", "k": k, "pattern": p, "bits": bits})
            pub_meta.append({"spec": {"kind": "angle", "k": k, "pattern": p,
                                      "bits": bits},
                             "placed_qubits": list(placed), "n_qubits": n})
            qcs.append(tc)

    sampler = SamplerV2(mode=backend)
    job = sampler.run([(qc, None, SHOTS) for qc in qcs])
    pending = {"suite": "k in " + str(list(KS)) + " x " + str(PATTERNS_PER_K),
               "snapshot": snap_path.name,
               "snapshot_fetched_at": snap.get("fetched_at"),
               "snapshot_last_update": snap.get("last_update_date"),
               "job_id": job.job_id(), "shots": SHOTS,
               "specs": specs, "pub_meta": pub_meta,
               "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    dest.write_text(json.dumps(pending, indent=2))
    print("submitted {} angle PUBs (k 9..18) -> {}".format(len(qcs), job.job_id()))
    return 0


def stage_collect():
    from qiskit_ibm_runtime import QiskitRuntimeService
    service = QiskitRuntimeService()
    pend_p = DATA / "j_real{}_pending.json".format("_refresh" if args.refresh else "")
    final_p = DATA / "j_real{}.json".format("_refresh" if args.refresh else "")
    if final_p.exists() and not args.force:
        print("already collected")
        return 0
    pending = json.loads(pend_p.read_text())
    job = service.job(pending["job_id"])
    if str(job.status()) != "DONE":
        print("status {}".format(job.status()))
        return 0
    result = job.result()
    rows = []
    for mi, meta in enumerate(pending["pub_meta"]):
        counts = result[mi].data.c.get_counts()
        n = meta["n_qubits"]
        total = sum(counts.values()) or 1
        bits = meta["spec"]["bits"]
        devs = []
        for i in range(n):
            p1 = sum(c for k, c in counts.items()
                     if len(k.replace(" ", "")) == n
                     and k.replace(" ", "")[::-1][i] == "1") / total
            w = window_mean(bits, i)
            devs.append(abs((1.0 - 2.0 * p1) - (1.0 - 2.0 * w)))
        rows.append({"k": meta["spec"]["k"], "pattern": meta["spec"]["pattern"],
                     "placed_qubits": meta["placed_qubits"],
                     "per_bit_dev": [round(d, 4) for d in devs],
                     "max_dev": round(max(devs), 4),
                     "pass_05": all(d <= TOL for d in devs)})
    out = dict(pending); out["rows"] = rows
    final_p.write_text(json.dumps(out, indent=2))
    for r in rows:
        print("k={:<2} p{} pass={} max_dev={:.4f}".format(r["k"], r["pattern"], r["pass_05"], r["max_dev"]))
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