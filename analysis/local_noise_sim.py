"""Matched local noise-model simulation for the sweep (task 5 baseline).

Same 19 weights, same pinned qubit, same transpilation -- but executed on
Aer with the CURRENT ibm_marrakesh calibration noise model instead of the
device. E_noise(w) from this run is directly comparable to E_QPU(w).
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from qpu_sweep import (  # noqa: E402
    N_TWIRL, SEED, SHOTS, WEIGHTS, _prop, build_circuit, gate_errors,
    pick_qubit, rotation_angle,
)

OUT = Path(__file__).resolve().parent.parent / "data" / "qpu_sweep"


def main() -> int:
    from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
    from qiskit_aer import AerSimulator
    from qiskit_aer.noise import NoiseModel
    from qiskit_ibm_runtime import QiskitRuntimeService

    backend = QiskitRuntimeService().backend("ibm_marrakesh")
    qi, calib = pick_qubit(backend)
    props = backend.properties()
    calib.update(gate_errors(props, qi))
    print("matched-noise sim on pinned qubit {}".format(qi))

    pm = generate_preset_pass_manager(
        backend=backend, optimization_level=1, seed_transpiler=SEED,
        initial_layout=[qi])
    noise = NoiseModel.from_backend(backend)
    sim = AerSimulator(noise_model=noise)

    rows = []
    for w in WEIGHTS:
        counts = sim.run(pm.run(build_circuit(rotation_angle(w))),
                         shots=SHOTS, seed_simulator=SEED).result().get_counts()
        p1 = counts.get("1", 0) / SHOTS
        rows.append({"w": w, "p1": p1,
                     "z_theory": 1.0 - 2.0 * w, "z_emp": 1.0 - 2.0 * p1,
                     "dev": abs((1.0 - 2.0 * p1) - (1.0 - 2.0 * w))})

    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / "sweep_localnoise.json"
    dest.write_text(json.dumps({
        "variant": "local_noise_model", "backend": "ibm_marrakesh",
        "shots": SHOTS, "seed_simulator": SEED, "weights": WEIGHTS,
        "calibration": calib, "rows": rows,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }, indent=2))
    mx = max(rows, key=lambda r: r["dev"])
    print("max dev: w={} dev={:.4f}".format(mx["w"], mx["dev"]))
    print("saved -> {}".format(dest.name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
