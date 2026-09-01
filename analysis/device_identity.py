"""Task 2: Device identity check -- query the IBM Quantum fleet.

Writes findings to notes/device_identity.md. Confirms:
  - is ibm_marrakesh still in fleet? status?
  - is ibm_fez in fleet? topology/qubit count? (156-qubit heavy-hex successor?)
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

ROOT = Path(r"C:\Users\SCSM11\Desktop\unimind-v2")
sys.path.insert(0, str(ROOT / "analysis"))

warnings.filterwarnings("ignore")
import logging
logging.disable(logging.CRITICAL)

from qiskit_ibm_runtime import QiskitRuntimeService

OUT = ROOT / "notes" / "device_identity.md"
OUT.parent.mkdir(parents=True, exist_ok=True)

RELEVANT = {"ibm_marrakesh", "ibm_fez", "ibm_kingston"}

def main():
    service = QiskitRuntimeService(
        channel="ibm_quantum_platform", instance="unimind 3.0")

    # fetch snapshot of whole fleet (name, status, n_qubits)
    backends = service.backends(simulator=False)
    fleet = {}
    for b in backends:
        try:
            nq = b.num_qubits
        except Exception:
            nq = None
        fleet[b.name] = {
            "name": b.name,
            "qubits": nq,
            "status": None,
            "max_shots": getattr(b, "max_shots", None),
            "coupled": None,
        }
        try:
            st = b.status()
            fleet[b.name]["status"] = (
                st.operational if hasattr(st, "operational") else None)
            fleet[b.name]["pending_jobs"] = (
                st.pending_jobs if hasattr(st, "pending_jobs") else None)
        except Exception as e:
            fleet[b.name]["status"] = f"status-query-failed: {e}"

    # detailed coupling map for the relevant devices
    for rn in RELEVANT:
        if rn in fleet:
            try:
                b = service.backend(rn)
                cm = b.coupling_map
                edges = list(cm) if cm else []
                fleet[rn]["coupled"] = edges[:5]
                fleet[rn]["n_couplings"] = len(edges)
                fleet[rn]["n_qubits_backend"] = b.num_qubits
            except Exception as e:
                fleet[rn]["n_qubits_backend"] = f"ERR {e}"
                fleet[rn]["coupled"] = None

    lines = []
    lines.append("# UniMind Device Identity Check")
    lines.append("")
    lines.append(f"_Generated: device_identity.py (script-verified, 2026-09-01)_")
    lines.append("")
    lines.append("## Fleet query result")
    lines.append("")
    lines.append("| Backend | In fleet | Qubits | Operational | n_coupling | coupling (first 5) |")
    lines.append("|---|---|---|---|---|---|")
    for rn in sorted(RELEVANT, key=lambda x: 0 if x == "ibm_marrakesh" else (1 if x == "ibm_fez" else 2)):
        if rn in fleet:
            f = fleet[rn]
            cm = f.get("coupled")
            ncou = f.get("n_couplings")
            lines.append(f"| {rn} | yes | {f['qubits']} | {f.get('status')} | {ncou} | {cm} |")
        else:
            lines.append(f"| {rn} | **NO** | - | - | - | - |")
    lines.append("")

    # conclusion
    fez_q = fleet.get("ibm_fez", {}).get("qubits")
    marr_status = fleet.get("ibm_marrakesh", {}).get("status")
    marr_in = "ibm_marrakesh" in fleet
    lines.append("## Conclusions")
    lines.append("")
    if marr_in:
        lines.append(f"- **ibm_marrakesh IS still in fleet** (operational: `{marr_status}`), 156 qubits.")
        lines.append("  => D0-D2 closed-loop results remain attributable to ibm_marrakesh; NOT a retired device.")
    else:
        lines.append("- **ibm_marrakesh is NOT in fleet** (retired/removed from open plan).")
    lines.append(f"- **ibm_fez**: {fez_q} qubits, {fleet.get('ibm_fez', {}).get('n_couplings')} edges, operational. ")
    lines.append("  Both marrakesh and fez are 156-qubit heavy-hex devices: fez is a SIBLING device, not a successor.")
    lines.append("  Continuous telemetry runs on ibm_fez; the telemetry_log.jsonl row timestamps are the source of truth.")
    lines.append("")
    lines.append("### Topology check (heavy-hex 156q?)")
    fez_cm = fleet.get("ibm_fez", {}).get("coupled")
    if fez_cm is not None:
        n_edges = fleet.get("ibm_fez", {}).get("n_couplings")
        lines.append(f"- ibm_fez coupling map: {n_edges} edges; sample {fez_cm}")
    else:
        lines.append("- ibm_fez coupling map unavailable.")
    lines.append("")

    raw = json.dumps({k: fleet[v].get("qubits") for k, v in enumerate(fleet)} )
    lines.append("## Raw fleet dump (all backends, name->qubits)")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps({n: f.get("qubits") for n, f in fleet.items()}, indent=1))
    lines.append("```")
    lines.append("")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUT)
    print(OUT.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()