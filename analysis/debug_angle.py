import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ablation_study import FULL_COVERAGE_TEMPLATES, _slot_bits, AblationLinkV2

it = "Encode the bits [1, 0, 1] into a quantum circuit using angle encoding."
low = it.lower()
for kw, body, fn in FULL_COVERAGE_TEMPLATES:
    if any(k in low for k in kw):
        p = fn(it)
        print("matched", kw, "| params:", p)
        code = body.format(**(p or {}))
        print("---- generated code ----")
        print(code)
        print("------------------------")
        link = AblationLinkV2(validation=True, heal=True, fallback=True)
        rep = link.healer.executor.run(code)
        print("success:", rep.success)
        print("error:", rep.error[:300])
        break
