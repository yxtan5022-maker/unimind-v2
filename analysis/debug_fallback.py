import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ablation_study import FULL_COVERAGE_TEMPLATES, _slot_fib
from bridge.healer import static_analysis

it = "Compute the 7th Fibonacci number and assign it to 'result'."
print("slot:", _slot_fib(it))
low = it.lower()
for kw, body, fn in FULL_COVERAGE_TEMPLATES:
    if any(k in low for k in kw):
        p = fn(it)
        print("matched", kw, "| params:", p)
        if p:
            code = body.format(**p)
            print("static_analysis:", static_analysis(code))
            rep_probe = None
            from bridge.healer import SandboxExecutor
            rep = SandboxExecutor().run(code)
            print("success:", rep.success)
            print("error:", rep.error[:200])
            print("traceback tail:", rep.traceback_text[-300:])
        break
