"""Tasks 3-5 -- systematic QPU weight sweep with pinned layout + matched noise sim.

Fixes two v1.7 confounds:
  * initial_layout pinned to ONE calibrated physical qubit (v1.7 let opt-level-1
    place freely, so bare vs mitigated may have hit different qubits);
  * N independent repeat jobs -> job-level variance for CIs.

For every submission we also record the calibration snapshot of the chosen
qubit (T1/T2/readout errors/sx error) so fitted distortion parameters can be
correlated with device physics (task 5).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "qpu_sweep"
SHOTS = 8192
SEED = 42
N_TWIRL = 16
WEIGHTS = [round(0.05 * k, 2) for k in range(1, 20)]


def rotation_angle(w: float) -> float:
    return 2.0 * math.asin(math.sqrt(w))


def build_circuit(theta: float):
    from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister
    qr, cr = QuantumRegister(1, "q"), ClassicalRegister(1, "c")
    qc = QuantumCircuit(qr, cr)
    qc.ry(theta, qr[0])
    qc.measure(qr[0], cr[0])
    return qc


def pick_qubit(backend) -> tuple[int, dict]:
    """Deterministic choice: minimise total readout assignment error."""
    props = backend.properties()
    best, best_err, snap = None, float("inf"), []
    for qi in range(backend.num_qubits):
        p01 = _prop(props, qi, "prob_meas0_prep1")
        p10 = _prop(props, qi, "prob_meas1_prep0")
        if p01 is None or p10 is None:
            continue
        tot = p01 + p10
        t1 = _prop(props, qi, "T1")
        t2 = _prop(props, qi, "T2")
        snap.append({"q": qi, "p01": p01, "p10": p10,
                     "readout_total": tot, "T1_us": t1, "T2_us": t2})
        if tot < best_err:
            best, best_err = qi, tot
    snap.sort(key=lambda d: d["readout_total"])
    return best, {"chosen_qubit": best, "top5": snap[:5],
                  "last_update_date": str(props.last_update_date)}


def _prop(props, qi: int, name: str):
    for item in props.qubits[qi]:
        if item.name == name:
            return item.value
    return None


def gate_errors(props, qi: int) -> dict:
    out = {}
    for gate in ("sx", "x", "id"):
        try:
            out["{}_error".format(gate)] = props.gate_error(gate, [qi])
        except Exception:
            out["{}_error".format(gate)] = None
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=["bare", "twirled"], required=True)
    ap.add_argument("--repeat", type=int, default=0)
    ap.add_argument("--backend", default="ibm_marrakesh")
    ap.add_argument("--no-pin", action="store_true",
                    help="reproduce v1.7 behaviour: let opt-level-1 place freely")
    ap.add_argument("--qubit", type=int, default=None,
                    help="override: pin explicitly to this physical qubit")
    args = ap.parse_args()

    from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
    from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2

    service = QiskitRuntimeService()
    backend = service.backend(args.backend)
    qi, calib = pick_qubit(backend)
    props = backend.properties()
    calib.update(gate_errors(props, qi))
    print("chosen qubit {} | readout(p01+p10)={:.5f} T1={:.1f}us T2={:.1f}us".format(
        qi, calib["top5"][0]["readout_total"],
        calib["top5"][0]["T1_us"] or -1, calib["top5"][0]["T2_us"] or -1))

    pm_kwargs = dict(backend=backend, optimization_level=1, seed_transpiler=SEED)
    target = args.qubit if args.qubit is not None else qi
    if not args.no_pin:
        pm_kwargs["initial_layout"] = [target]
    pm = generate_preset_pass_manager(**pm_kwargs)
    circuits = [pm.run(build_circuit(rotation_angle(w))) for w in WEIGHTS]
    try:
        placed = circuits[0].layout.initial_index_layout(filter_ancillas=True)[0]
    except Exception:
        placed = None

    options = None
    if args.variant == "twirled":
        options = {"twirling": {"enable_measure": True,
                                 "num_randomizations": N_TWIRL}}
    sampler = SamplerV2(mode=backend, options=options)
    job = sampler.run([(qc, None, SHOTS) for qc in circuits])
    print("job submitted:", job.job_id())
    result = job.result(timeout=7200)

    rows = []
    for i, w in enumerate(WEIGHTS):
        counts = result[i].data.c.get_counts()
        p1 = counts.get("1", 0) / SHOTS
        rows.append({"w": w, "p1": p1, "shots": SHOTS,
                     "z_theory": 1.0 - 2.0 * w, "z_emp": 1.0 - 2.0 * p1,
                     "dev": abs((1.0 - 2.0 * p1) - (1.0 - 2.0 * w))})

    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / "sweep_{}_r{}.json".format(args.variant, args.repeat)
    dest.write_text(json.dumps({
        "variant": args.variant, "repeat": args.repeat,
        "backend": args.backend, "job_id": job.job_id(),
        "shots": SHOTS, "seed_transpiler": SEED, "weights": WEIGHTS,
        "pinned": not args.no_pin, "placed_qubit": placed, "chosen_qubit": qi,
        "calibration": calib, "rows": rows,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }, indent=2))
    print("saved -> {}".format(dest.name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
