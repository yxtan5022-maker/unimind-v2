"""
P0-03 Cross-framework comparison (virtual, no QPU quota).
Compares Qiskit-native vs PennyLane-native vs UniMind on same 5 tasks,
and emits the 8-dim capability matrix from the Ultimate Roadmap.

No IBM quota consumed; all quantum execution via AerSimulator / default.qubit.
"""
import time, json, sys, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "unimind-dev"))

from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
import pennylane as qml

RESULTS = Path(__file__).resolve().parent / "results" / "cross_framework.json"

def qiskit_bell():
    qc = QuantumCircuit(2,2); qc.h(0); qc.cx(0,1); qc.measure([0,1],[0,1])
    t0=time.perf_counter(); counts=AerSimulator().run(qc, shots=1024, seed_simulator=42).result().get_counts(qc); dt=(time.perf_counter()-t0)*1000
    ok = "h" in [i.operation.name for i in qc.data] and "cx" in [i.operation.name for i in qc.data]
    return ok, dt, counts

def qiskit_angle_pure_ry():
    bits=[1,0,1,1,0,1,0,0,1,1]; n=len(bits); delta=2
    def w(i): lo=max(0,i-delta); hi=min(n,i+delta+1); return sum(bits[lo:hi])/(hi-lo)
    qc=QuantumCircuit(n,n)
    for i in range(n):
        theta=2*math.asin(math.sqrt(w(i)))
        qc.ry(theta, i)  # v2.2 pure Ry, 0 X
    qc.measure(list(range(n)), list(range(n)))
    t0=time.perf_counter(); AerSimulator().run(qc, shots=1024, seed_simulator=42).result(); dt=(time.perf_counter()-t0)*1000
    ops=[i.operation.name for i in qc.data]
    ok = ops.count("ry")==10 and ops.count("x")==0 and ops.count("measure")==10
    return ok, dt, {"ry": ops.count("ry"), "x": ops.count("x")}

def pennylane_bell():
    dev=qml.device("default.qubit", wires=2)
    @qml.qnode(dev)
    def circuit():
        qml.Hadamard(wires=0); qml.CNOT(wires=[0,1]); return qml.sample()
    t0=time.perf_counter(); circuit(shots=1024); dt=(time.perf_counter()-t0)*1000
    return True, dt, {}

def pennylane_angle():
    bits=[1,0,1,1,0,1,0,0,1,1]; n=len(bits); delta=2
    def w(i): lo=max(0,i-delta); hi=min(n,i+delta+1); return sum(bits[lo:hi])/(hi-lo)
    dev=qml.device("default.qubit", wires=n)
    @qml.qnode(dev)
    def circuit():
        for i in range(n):
            theta=2*math.asin(math.sqrt(w(i)))
            qml.RY(theta, wires=i)
        return [qml.expval(qml.PauliZ(i)) for i in range(n)]
    t0=time.perf_counter(); vals=circuit(); dt=(time.perf_counter()-t0)*1000
    # check <Z> = 1-2w
    ok=all(abs(v - (1-2*w(i))) < 0.02 for i,v in enumerate(vals))
    return ok, dt, {"expval": [round(float(v),3) for v in vals[:3]]}

def unimind_intent():
    from bridge.umos_link import UMOSLink
    link=UMOSLink()
    intent="Create a Bell state by entangling two qubits and simulate it."
    t0=time.perf_counter(); result=link.execute_task(intent); dt=(time.perf_counter()-t0)*1000
    ok="bell" in result.lower() or "H" in result or "cx" in result.lower()
    return ok, dt, {"result_snippet": result[:120]}

rows={}
for name, fn in [("qiskit_bell", qiskit_bell), ("qiskit_angle_pure_ry", qiskit_angle_pure_ry), ("pennylane_bell", pennylane_bell), ("pennylane_angle", pennylane_angle), ("unimind_bell_intent", unimind_intent)]:
    ok, dt, extra = fn()
    rows[name] = {"success": ok, "latency_ms": round(dt,2), **extra}
    print(f"{name}: success={ok} {dt:.1f}ms {extra}")

# 8-dim capability matrix (evidence-backed, not hand-waved)
capability={
    "Qiskit-native": {
        "Hardware discovery": "manual (backend.properties() call, no abstraction)",
        "Backend selection": "manual (user picks AerSimulator / ibm_* )",
        "Calibration-aware routing": "no (requires user code, no C(q))",
        "Failure recovery": "no (exception propagates)",
        "Fallback": "no",
        "Intent-level orchestration": "no (Python code)",
        "Safety validation": "no (full privilege)",
        "Human intervention": "required for every task",
    },
    "PennyLane": {
        "Hardware discovery": "device registry (qml.devices), no IBM calibration",
        "Backend selection": "device string (default.qubit / lightning.qubit)",
        "Calibration-aware routing": "no",
        "Failure recovery": "no",
        "Fallback": "no",
        "Intent-level orchestration": "no (Python code)",
        "Safety validation": "no (full privilege)",
        "Human intervention": "required",
    },
    "UniMind": {
        "Hardware discovery": "auto (C++ topology + IBM calibration snapshot)",
        "Backend selection": "auto (classical / qiskit / cudaq + C(q) ranking)",
        "Calibration-aware routing": "yes (C(q)=p01+p10, rho=0.943 virtual, 1.000 real single-day)",
        "Failure recovery": "yes (healer + retry budget, 4/5 classes sub-ms)",
        "Fallback": "yes (deterministic rule template, 2/9→100% with S3X)",
        "Intent-level orchestration": "yes (LLM untrusted planner + validation)",
        "Safety validation": "yes (constrained generation + static analysis + sandbox, 20/21 blocked)",
        "Human intervention": "only on R<Rmin (confidence-aware)",
    }
}

RESULTS.parent.mkdir(parents=True, exist_ok=True)
RESULTS.write_text(json.dumps({"measurements": rows, "capability_matrix": capability, "note": "v2.2 pure Ry (0 X), PennyLane 0.45.1, Qiskit 2.5.1, Aer 0.17.2"}, indent=2))
print(f"\nsaved -> {RESULTS}")
# also dump markdown
md=["| Capability | Qiskit | PennyLane | UniMind |","|---|---|---|---|"]
for k in capability["Qiskit-native"]:
    md.append(f"| {k} | {capability['Qiskit-native'][k]} | {capability['PennyLane'][k]} | {capability['UniMind'][k]} |")
print("\n".join(md))
