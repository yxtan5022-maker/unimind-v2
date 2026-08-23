"""Shared instrumented mock-LLM harness for v2.0 experiments.

Records EVERY LLM call outcome (ground-truth / broken-template index /
unavailable) per pipeline stage (generation vs healing), so injected fault
classes are known exactly -- unlike the frozen v1.7 results.
"""
from __future__ import annotations

import io
import contextlib
import random
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent / "unimind-dev"
sys.path.insert(0, str(REPO))

from experiments.llm_reliability import (  # noqa: E402
    _ADVERSARIAL_CODE,
    _BROKEN_TEMPLATES,
    generate_tasks,
)
from bridge.umos_link import UMOSLink  # noqa: E402

FAULT_CLASS = {
    0: "runtime_zero_division",
    1: "name_error",
    2: "syntax_error",
    3: "syntax_error",
    4: "import_violation",
    5: "syntax_error",
}


class InstrumentedMock:
    """Same stochastic policy as v1.7 mock, plus full call-level logging."""

    def __init__(self, quality: float, failrate: float, seed: int):
        self.quality = quality
        self.failrate = failrate
        self.rng = random.Random(seed)
        self.log: list[dict] = []

    def binder(self, task_id: str, stage: str, state: dict):
        def mock_chat(prompt: str = "", system: str = "", cfg=None):
            r = self.rng.random()
            if state["cls"] == "adversarial":
                out = _ADVERSARIAL_CODE
                tag = "adversarial_code"
            elif r < self.failrate:
                out = None
                tag = "unavailable"
            elif r < self.quality + self.failrate:
                out = state["gt"]
                tag = "ground_truth"
            else:
                idx = self.rng.randrange(len(_BROKEN_TEMPLATES))
                out = _BROKEN_TEMPLATES[idx]
                tag = "broken:{}".format(idx)
            self.log.append({"task": task_id, "stage": stage, "tag": tag})
            state["calls"] += 1
            return out
        return mock_chat


def run_one_config(link: UMOSLink, mock: InstrumentedMock, tasks: list[dict]) -> list[dict]:
    import bridge.umos_link as umos_mod
    import bridge.healer as healer_mod

    orig_gen, orig_heal = umos_mod.chat, healer_mod.chat
    rows: list[dict] = []
    try:
        for task in tasks:
            state = {"cls": task["class"], "gt": task.get("gt"), "calls": 0}
            t0 = time.perf_counter()
            umos_mod.chat = mock.binder(task["id"], "gen", state)
            healer_mod.chat = mock.binder(task["id"], "heal", state)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                result = link.execute_task(task["intent"])
            lat = (time.perf_counter() - t0) * 1000.0

            row = {
                "id": task["id"], "class": task["class"], "kind": task["kind"],
                "latency_ms": lat, "llm_calls": state["calls"], "raw": result[:300],
            }
            fb = "RULE_BASED_FALLBACK" in result
            healed = "HEALED" in result
            vf = "static analysis" in result or "VALIDATION_REJECTED" in result
            if task["class"] == "adversarial":
                refused = ("HEAL_FAILED" in result or "FALLBACK_FAILED" in result
                           or "static analysis" in result or "rejected" in result
                           or "no matching" in result.lower())
                executed = "pwned" in result or "files deleted" in result
                row["success"] = refused and not executed
                row["path"] = "rejected" if row["success"] else "BREACH"
            else:
                ok = ("LLM_EXECUTED" in result or "HEALED" in result
                      or "RULE_BASED_FALLBACK" in result)
                fail = "HEAL_FAILED" in result or "FALLBACK_FAILED" in result \
                    or "FAIL_NO_LLM" in result
                row["success"] = ok and not fail
                if fb:
                    row["path"] = "fallback_ok" if row["success"] else "fallback_failed"
                elif healed:
                    row["path"] = "healed" if row["success"] else "heal_failed"
                elif vf:
                    row["path"] = "validation_rejected"
                elif "LLM_EXECUTED" in result:
                    row["path"] = "first_pass" if row["success"] else "exec_failed"
                else:
                    row["path"] = "failed_other"
            rows.append(row)
    finally:
        umos_mod.chat, healer_mod.chat = orig_gen, orig_heal
    return rows


def first_injected_fault(mock: InstrumentedMock, task_id: str):
    """Fault class injected on the FIRST generation call, else None."""
    for e in mock.log:
        if e["task"] != task_id or e["stage"] != "gen":
            continue
        if e["tag"].startswith("broken"):
            return int(e["tag"].split(":")[1])
        return None
    return None


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    import math
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


__all__ = ["InstrumentedMock", "run_one_config", "first_injected_fault",
           "generate_tasks", "UMOSLink", "wilson", "FAULT_CLASS"]
