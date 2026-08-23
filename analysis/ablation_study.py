"""Task 1 -- architectural ablation S0..S3 on the UniMind orchestration stack.

Stages (substrate = SandboxExecutor, held constant):
  S0  generation (<=3 attempts) + execution
  S1  + static-analysis validation verdict (fail-fast gate)
  S2  + self-healing loop
  S3  + rule-based fallback on LLM unavailability
"""
import argparse
import io
import contextlib
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mock_llm import InstrumentedMock, generate_tasks, run_one_config, wilson  # noqa: E402

REPO = Path(__file__).resolve().parent.parent / "unimind-dev"
sys.path.insert(0, str(REPO))

from bridge.healer import static_analysis  # noqa: E402
from bridge.umos_link import UMOSLink  # noqa: E402

OUT = Path(__file__).resolve().parent / "results"


class AblationLink(UMOSLink):
    def __init__(self, validation: bool, heal: bool, fallback: bool):
        super().__init__("ablation")
        self.use_validation = validation
        self.use_heal = heal
        self.use_fallback = fallback

    def execute_task(self, task_description: str) -> str:
        code = None
        for attempt in range(self.llm_max_retries):
            code = self.generate_code(task_description)
            if code is not None:
                break

        used_fallback = False
        if code is None:
            if not self.use_fallback:
                return "FAIL_NO_LLM"
            code = self.rule_based_fallback(task_description)
            used_fallback = True

        if self.use_validation and static_analysis(code) is not None:
            return ("VALIDATION_REJECTED" if not used_fallback
                    else "FALLBACK_FAILED")

        report = io.StringIO()
        with contextlib.redirect_stdout(report):
            res = self.healer.executor.run(code)

        if res.success:
            prefix = "RULE_BASED_FALLBACK" if used_fallback else "LLM_EXECUTED"
            return "{}: {}".format(prefix, res.output[:300])
        if used_fallback:
            return "FALLBACK_FAILED: {}".format(res.error[:100])
        if not self.use_heal:
            return "EXEC_FAILED: {}".format(res.error[:100])

        with contextlib.redirect_stdout(report):
            healed = self.healer.heal(task_description)
        if healed.success:
            return "HEALED: {}".format(healed.output[:300])
        return "HEAL_FAILED: {}".format(healed.error[:100])


CONFIGS = {
    "S0": dict(validation=False, heal=False, fallback=False),
    "S1": dict(validation=True, heal=False, fallback=False),
    "S2": dict(validation=True, heal=True, fallback=False),
    "S3": dict(validation=True, heal=True, fallback=True),
    "S3X": dict(validation=True, heal=True, fallback=True),
}

import re


def _slot_fib(intent):
    m = re.search(r"(\d+)(?:st|nd|rd|th)? Fibonacci", intent)
    return {"n": m.group(1)} if m else None


def _slot_primes(intent):
    m = re.search(r"first (\d+) prime", intent)
    return {"n": m.group(1)} if m else None


def _slot_squares(intent):
    m = re.search(r"from 1 to (\d+)", intent)
    return {"n": m.group(1)} if m else None


def _slot_str(intent):
    m = re.search(r'string "(.*?)"', intent)
    return {"s": m.group(1)} if m else None


def _slot_mean(intent):
    m = re.search(r"values \[(.*?)\]", intent)
    return {"n": m.group(1)} if m else None


def _slot_bits(intent):
    m = re.search(r"bits (\[.*?\])", intent)
    return {"bits": m.group(1)} if m else None


FULL_COVERAGE_TEMPLATES = (
    (("fibonacci",), (
        "a, b = 0, 1\n"
        "for _ in range({n}):\n"
        "    a, b = b, a + b\n"
        "result = a"
    ), _slot_fib),
    (("prime",), (
        "count, cand, total = 0, 2, 0\n"
        "while count < {n}:\n"
        "    is_p = all(cand % d for d in range(2, int(cand ** 0.5) + 1))\n"
        "    if is_p:\n"
        "        total += cand\n"
        "        count += 1\n"
        "    cand += 1\n"
        "result = total"
    ), _slot_primes),
    (("squares",), (
        "result = sum(i * i for i in range(1, {n} + 1))"
    ), _slot_squares),
    (("reverse",), (
        'result = "{s}"[::-1]'
    ), _slot_str),
    (("mean", "average"), (
        "values = [{n}]\n"
        "result = sum(values) / len(values)"
    ), _slot_mean),
    (("palindrome",), (
        'result = "{s}" == "{s}"[::-1]'
    ), _slot_str),
    (("ghz",), (
        "from qiskit import QuantumCircuit\n"
        "qc = QuantumCircuit(3, 3)\n"
        "qc.h(0)\n"
        "qc.cx(0, 1)\n"
        "qc.cx(1, 2)\n"
        "qc.measure([0, 1, 2], [0, 1, 2])\n"
        "result = 'GHZ state circuit prepared (rule-based fallback)'"
    ), lambda intent: {}),
    (("angle", "encode"), (
        "import math\n"
        "from qiskit import QuantumCircuit\n"
        "bits = {bits}\n"
        "qc = QuantumCircuit(len(bits), len(bits))\n"
        "for i, bit in enumerate(bits):\n"
        "    theta = 2 * math.asin(math.sqrt(0.5))\n"
        "    qc.ry(theta, i)\n"
        "    if bit == 1:\n"
        "        qc.x(i)\n"
        "qc.measure(range(len(bits)), range(len(bits)))\n"
        "result = 'angle-encoded ' + str(len(bits)) + ' qubits'"
    ), _slot_bits),
)


class FullCoverageFallbackMixin:
    def rule_based_fallback(self, intent: str) -> str:
        low = intent.lower()
        for keywords, body, slot_fn in FULL_COVERAGE_TEMPLATES:
            if any(k in low for k in keywords):
                params = slot_fn(intent)
                if params is None:
                    break
                try:
                    return body.format(**params) + "\n"
                except (KeyError, ValueError, IndexError):
                    break
        return super().rule_based_fallback(intent)


class AblationLinkV2(FullCoverageFallbackMixin, AblationLink):
    pass


def build_link(tag: str):
    cls = AblationLinkV2 if tag == "S3X" else AblationLink
    return cls(**CONFIGS[tag])


def run_grid(runs, n_valid=150, n_adv=10):
    all_rows = []
    for tag, q, fr, seed in runs:
        tasks = generate_tasks(n_valid, n_adv, seed)
        mock = InstrumentedMock(q, fr, seed)
        link = build_link(tag)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rows = run_one_config(link, mock, tasks)
        valid = [r for r in rows if r["class"] == "valid"]
        succ = sum(r["success"] for r in valid)
        lo, hi = wilson(succ, len(valid))
        lat = sorted(r["latency_ms"] for r in valid)
        paths = Counter(r["path"] for r in valid)
        adv = [r for r in rows if r["class"] == "adversarial"]
        breaches = sum(1 for r in adv if r["path"] == "BREACH")
        rec = {"stage": tag, "q": q, "failrate": fr, "seed": seed,
               "n_valid": len(valid), "success": succ,
               "ci95": [round(lo, 4), round(hi, 4)],
               "median_ms": round(lat[len(lat) // 2], 3),
               "paths": dict(paths),
               "adversarial_breaches": breaches}
        all_rows.append(rec)
        print("{:>2} q={} fr={} seed={}: {:>3}/{} = {:5.1f}%  med={:.1f}ms  {}".format(
            tag, q, fr, seed, succ, len(valid), 100 * succ / len(valid),
            rec["median_ms"], dict(paths)))
    return all_rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", choices=["quality", "stress", "stress2"], required=True)
    args = ap.parse_args()

    OUT.mkdir(exist_ok=True)
    seeds = (42, 43, 44)
    if args.part == "quality":
        runs = [(t, q, 0.1, s) for q in (0.5, 0.7, 0.9) for s in seeds
                for t in ("S0", "S1", "S2", "S3")]
    elif args.part == "stress":
        runs = [(t, 0.7, fr, s) for fr in (0.3, 0.5) for s in seeds
                for t in ("S2", "S3")]
    else:
        runs = [(t, 0.7, fr, s) for fr in (0.3, 0.5) for s in seeds
                for t in ("S2", "S3X")]

    rows = run_grid(runs)
    dest = OUT / "ablation_{}.json".format(args.part)
    dest.write_text(json.dumps(rows, indent=2))
    print("saved -> {}".format(dest.name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
