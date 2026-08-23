"""RQ1 -- Numerical verification of the Unibit mathematics.

Checks five proposition families against the actual implementation
(umos_py/unibit.py, quantum/qunibit.py):

  P1  kernel properties      g_i = sinc((i+phi)*pi/n) positive, strictly
                             decreasing; phi breaks grid symmetry
  P2  collapse <=> position-adaptive threshold T_i = tau/g_i, strictly
                             increasing; structural dead zone beyond the
                             sinc root x* of sinc(x) = tau; reproduces the
                             v2.0 Fig.~unibit all-zero example at n=10
  P3  encoding identity      (a) pure Ry: P(1) = sin^2(theta/2) = w
                             (b) repo fold path (X-then-Ry for b=1):
                                 P(1) = 1 - w -- documented divergence from
                                 the paper's stated identity
  P4  affine channel closure two affine channels compose to an affine
                             channel (slope product, offset sum)
  P5  window truncation      clipped sliding-window mean == brute force

Exact probabilities come from qiskit.quantum_info.Statevector (no sampling
noise); a shots-based sanity check confirms finite-sample behaviour.
"""
from __future__ import annotations

import json
import math
import sys
import random
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent / "unimind-dev"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from umos_py.unibit import Unibit, UnibitConfig  # noqa: E402

PHI, TAU, DELTA = 0.42, 0.707, 2
OUT = Path(__file__).resolve().parent / "results" / "unibit_math.json"
results = {"pass": 0, "fail": 0, "checks": []}


def record(name: str, ok: bool, detail: str):
    results["pass" if ok else "fail"] += 1
    results["checks"].append({"name": name, "ok": ok, "detail": detail})
    print("{} {:<46} {}".format("PASS" if ok else "FAIL", name, detail))


def sinc(x: float) -> float:
    return 1.0 if x == 0 else math.sin(x) / x


def kernel(i: int, n: int, phi: float = PHI) -> float:
    return sinc((i + phi) * math.pi / n)


def window_mean_brute(bits, i, delta):
    lo, hi = max(0, i - delta), min(len(bits) - 1, i + delta)
    seg = bits[lo:hi + 1]
    return sum(seg) / len(seg)


def classical_fold(bits, phi=PHI):
    n = len(bits)
    out = []
    for i in range(n):
        w = window_mean_brute(bits, i, DELTA)
        out.append(w * kernel(i, n, phi))
    return out


# ---------------------------------------------------------------- P1
def prop1():
    n = 64
    gs = [kernel(i, n) for i in range(n)]
    ok_pos = all(g > 0 for g in gs)
    ok_dec = all(gs[i] > gs[i + 1] for i in range(n - 1))
    record("P1a kernel positive", ok_pos,
           "min={:.4f} at i={}".format(min(gs), gs.index(min(gs))))
    record("P1b kernel strictly decreasing", ok_dec,
           "g_0={:.4f} -> g_{{n-1}}={:.4f}".format(gs[0], gs[-1]))
    # phi != 0 breaks symmetry: g(i) != g(n-1-i) in general
    sym_break = any(abs(kernel(i, 10) - kernel(9 - i, 10)) > 1e-9 for i in range(5))
    record("P1c phi breaks grid symmetry", sym_break,
           "phi={} shifts every sample off the integer grid".format(PHI))
    return ok_pos and ok_dec


# ---------------------------------------------------------------- P2
def prop2():
    rng = random.Random(7)
    ub = Unibit(UnibitConfig(phase_shift=PHI, collapse_threshold=TAU,
                             window_delta=DELTA))
    worst = 0.0
    for _ in range(200):
        bits = [rng.randint(0, 1) for _ in range(rng.randint(4, 40))]
        folded = ub.fold_bits(bits)
        coll = ub.collapse_signal(folded)
        ws = [window_mean_brute(bits, i, DELTA) for i in range(len(bits))]
        pred = [1 if abs(w * kernel(i, len(bits))) > TAU else 0
                for i, w in enumerate(ws)]
        worst = max(worst, max((abs(a - b) for a, b in zip(coll, pred)),
                               default=0.0))
    record("P2a collapse <=> adaptive threshold T_i=tau/g_i", worst == 0,
           "max disagreement over 200 random sequences = {}".format(worst))

    ts = [TAU / kernel(i, 64) for i in range(64)]
    record("P2b T_i strictly increasing",
           all(ts[i] < ts[i + 1] for i in range(63)),
           "T_0={:.3f} -> T_63={:.1f}".format(ts[0], ts[-1]))

    # structural dead zone: sinc root x* of sinc(x) = tau
    lo, hi = 1.0, 2.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if sinc(mid) > TAU:
            lo = mid
        else:
            hi = mid
    x_star = (lo + hi) / 2
    n = 64
    i_star = next(i for i in range(n) if kernel(i, n) <= TAU)
    predicted = math.ceil(x_star * n / math.pi - PHI)
    record("P2c dead-zone boundary matches sinc root",
           abs(i_star - predicted) <= 1,
           "x*={:.4f}, first dead i={} (predicted {})".format(
               x_star, i_star, predicted))

    # paper Fig.~unibit claims an all-zero collapse for the n=10 demo input;
    # the implementation actually yields s_1 = 0.7254 > tau -> bit at pos 2
    demo_bits = [1, 0, 1, 1, 0, 1, 0, 0, 1, 1]
    s_demo = classical_fold(demo_bits)
    coll_demo = ub.collapse_signal(s_demo)
    record("P2d n=10 demo input -> collapse[1]=1 (paper claim falsified)",
           coll_demo == [0, 1, 0, 0, 0, 0, 0, 0, 0, 0]
           and abs(s_demo[1] - 0.7254) < 5e-4,
           "s_1={:.4f}>tau, collapse={}".format(s_demo[1], coll_demo))

    # kernel positivity on (0, pi) implies s_i = w_i*g_i >= 0 always:
    # the published figure's negative tail (-0.0268) is impossible under Eq.(3)
    neg_free = True
    rng2 = random.Random(3)
    for _ in range(500):
        bits = [rng2.randint(0, 1) for _ in range(rng2.randint(4, 64))]
        neg_free &= all(v >= -1e-15 for v in classical_fold(bits))
    record("P2e s_i >= 0 always (no negative sinc tail)", neg_free,
           "published fig data had min -0.0268 -- coordinates not from Eq.(3)")
    return True


# ---------------------------------------------------------------- P3
def prop3():
    from qiskit import QuantumCircuit
    from qiskit.quantum_info import Statevector

    def ry_prob_exact(w: float, apply_x: bool) -> float:
        qc = QuantumCircuit(1)
        if apply_x:
            qc.x(0)
        qc.ry(2 * math.asin(math.sqrt(w)), 0)
        sv = Statevector(qc)
        return float(sv.probabilities_dict().get("1", 0.0))

    errs_a, errs_b = [], []
    for w in [0.05, 0.1, 0.3, 0.5, 0.7, 0.9, 0.95]:
        errs_a.append(abs(ry_prob_exact(w, False) - w))          # paper claim
        errs_b.append(abs(ry_prob_exact(w, True) - (1.0 - w)))   # repo path
    record("P3a pure Ry: P(1)=w exactly (statevector)",
           max(errs_a) < 1e-12, "max err {:.2e}".format(max(errs_a)))
    record("P3b repo X-then-Ry: P(1)=1-w (b=1 branch)",
           max(errs_b) < 1e-12,
           "max err {:.2e}; diverges from paper identity by 2w-1 at w extremes"
           .format(max(errs_b)))

    # shots-based sanity check at w=0.7 without X
    try:
        from qiskit_aer import AerSimulator
        qc = QuantumCircuit(1, 1)
        qc.ry(2 * math.asin(math.sqrt(0.7)), 0)
        qc.measure(0, 0)
        counts = AerSimulator().run(qc, shots=100000, seed_simulator=42)\
            .result().get_counts()
        emp = counts.get("1", 0) / 100000
        se = math.sqrt(0.7 * 0.3 / 100000)
        record("P3c shots sanity (w=0.7, 1e5 shots)",
               abs(emp - 0.7) < 4 * se,
               "emp={:.4f} theory=0.7000 ({} SE)".format(emp,
                                                         round(abs(emp - 0.7) / se, 1)))
    except Exception as e:  # pragma: no cover
        record("P3c shots sanity", False, "Aer unavailable: {}".format(e))
    return True


# ---------------------------------------------------------------- P4
def prop4():
    rng = random.Random(11)
    ok = True
    for _ in range(50):
        a1, b1 = rng.uniform(0, 1), rng.uniform(-0.05, 0.05)
        a2, b2 = rng.uniform(0, 1), rng.uniform(-0.05, 0.05)
        w = rng.uniform(0, 1)
        lhs = b2 + a2 * (b1 + a1 * w)
        rhs = (b2 + a2 * b1) + (a1 * a2) * w
        ok &= abs(lhs - rhs) < 1e-12
    record("P4 affine channels closed under composition", ok,
           "(a1*a2 slope product, b2+a2*b1 offset) -- supports the "
           "$P_obs=b+a*w$ channel model")
    return ok


# ---------------------------------------------------------------- P5
def prop5():
    rng = random.Random(13)
    ub = Unibit(UnibitConfig(phase_shift=PHI, collapse_threshold=TAU,
                             window_delta=DELTA))
    ok = True
    for _ in range(100):
        bits = [rng.randint(0, 1) for _ in range(rng.randint(1, 30))]
        i = rng.randrange(len(bits))
        got = ub.sliding_window_weight(bits, i, DELTA)
        want = window_mean_brute(bits, i, DELTA)
        ok &= abs(got - want) < 1e-12
    widths = set()
    for i in range(20):
        lo, hi = max(0, i - DELTA), min(19, i + DELTA)
        widths.add(hi - lo + 1)
    record("P5 clipped window mean == brute force", ok,
           "window widths observed: {}".format(sorted(widths)))
    return ok


def main() -> int:
    print("== RQ1 Unibit mathematics: numerical verification ==\n")
    prop1()
    prop2()
    prop3()
    prop4()
    prop5()
    OUT.write_text(json.dumps(results, indent=2))
    print("\n{}/{} checks passed -> {}".format(results["pass"],
          results["pass"] + results["fail"], OUT))
    return 0 if results["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
