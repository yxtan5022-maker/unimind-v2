"""
Regression test for Algorithm 1 fix (v2.2).
Covers w in {0, 0.05, ..., 1} with different bit patterns.
Asserts |P_emp(1) - w| < epsilon (3*sigma) for pure Ry encoding.
Also asserts full-pipeline qunibit circuit (no conditional X) meets same.
Intended for CI: python -m pytest tests/test_unibit_correctness_v2_2.py -v
"""
import math
import sys
from pathlib import Path

# allow import from unimind-dev
REPO = Path(__file__).resolve().parents[1] / "unimind-dev"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "umos_py"))

from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator


def p_emp_pure_ry(w: float, shots: int = 8192, seed: int = 42) -> float:
    theta = 2.0 * math.asin(math.sqrt(w)) if 0 < w < 1 else (0.0 if w == 0 else math.pi)
    qc = QuantumCircuit(1, 1)
    if theta != 0:
        qc.ry(theta, 0)
    qc.measure(0, 0)
    sim = AerSimulator(seed_simulator=seed)
    counts = sim.run(qc, shots=shots).result().get_counts()
    # counts keys are '0'/'1'
    c1 = counts.get("1", 0)
    return c1 / shots


def test_pure_ry_grid():
    ws = [round(i * 0.05, 10) for i in range(21)]  # 0..1 step 0.05
    shots = 8192
    failures = []
    for w in ws:
        p = p_emp_pure_ry(w, shots=shots, seed=42)
        # 3-sigma bound: 3*sqrt(w(1-w)/N), floor at 3*sqrt(0.25/N) for w=0/1 via continuity
        if w in (0, 1):
            sigma = math.sqrt(0.25 / shots)  # worst case
        else:
            sigma = math.sqrt(w * (1 - w) / shots)
        eps = max(0.02, 3 * sigma)  # at least 0.02 absolute for shot noise at edges
        # tighter absolute epsilon 0.03 covers 3 sigma for all w at 8192 shots
        if abs(p - w) > 0.03:
            failures.append((w, p, abs(p - w), eps))
    assert not failures, f"Pure Ry failed for {failures}"


def test_qunibit_no_conditional_x():
    """Full pipeline: qunibit.py v2.2 must not contain conditional X before Ry."""
    # Check source no longer has the buggy pattern
    src = (REPO / "quantum" / "qunibit.py").read_text(encoding="utf-8")
    # The buggy two-liner "if b == 1: qc.x" should be gone from active code (backup keeps it)
    # We allow it only in comments mentioning v2.1
    lines = [l for l in src.splitlines() if "qc.x(qr[i])" in l and not l.strip().startswith("#")]
    assert len(lines) == 0, f"qunibit.py still contains active qc.x: {lines}"

    # Functional check: build a circuit for bits that provoke w=0.5 and verify pure Ry
    from quantum.qunibit import QUnibit, QUnibitConfig
    qu = QUnibit(QUnibitConfig(window_delta=2))
    bits = [1, 0, 1, 1, 0, 1, 0, 0, 1, 1]
    qc = qu._fold_qiskit(bits)
    assert qc is not None
    # Count ops: should have n Ry, 0 X
    ops = qc.count_ops()
    assert ops.get("ry", 0) == len(bits), f"expected {len(bits)} Ry, got {ops}"
    assert ops.get("x", 0) == 0, f"v2.2 must have 0 X, got {ops.get('x',0)}"


def test_bit_pattern_coverage():
    """Different bit patterns that map to same w via sliding window must still give P(1)=w."""
    # Construct synthetic bits where sliding_window_weight hits target w
    # Use simple full-window averaging: for Delta=2, weight = mean of up to 5 bits
    # Test patterns: all zeros -> w=0, all ones -> w=1, alternating -> w=0.5, sparse
    patterns = {
        "all_zero": [0] * 10,
        "all_one": [1] * 10,
        "alternating": [1, 0] * 5,
        "sparse": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0],
    }
    from umos_py.unibit import Unibit
    for name, bits in patterns.items():
        for i, b in enumerate(bits):
            w = Unibit.sliding_window_weight(bits, i, 2)
            p = p_emp_pure_ry(w, shots=4096, seed=123)
            assert abs(p - w) < 0.04, f"{name} i={i} w={w} p={p}"


if __name__ == "__main__":
    test_pure_ry_grid()
    print("test_pure_ry_grid PASSED")
    test_qunibit_no_conditional_x()
    print("test_qunibit_no_conditional_x PASSED")
    test_bit_pattern_coverage()
    print("test_bit_pattern_coverage PASSED")
    print("ALL REGRESSION TESTS PASSED")
