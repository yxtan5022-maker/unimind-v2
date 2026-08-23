import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ablation_study import AblationLinkV2

link = AblationLinkV2(validation=True, heal=True, fallback=True)
tests = [
    "Compute the 7th Fibonacci number and assign it to 'result'.",
    "Compute the sum of the first 5 prime numbers and assign it to 'result'.",
    "Compute the sum of squares of integers from 1 to 9 and assign it to 'result'.",
    'Reverse the string "hello" and assign the result to \'result\'.',
    "Compute the mean of the values [3, 7, 9, 21] and assign it to 'result'.",
    'Check whether the string "racecar" is a palindrome.',
    "Create a GHZ state circuit on three qubits and assign the circuit to 'qc'.",
    "Encode the bits [1, 0, 1] into a quantum circuit using angle encoding.",
]
ok = 0
for it in tests:
    code = link.rule_based_fallback(it)
    rep = link.healer.executor.run(code)
    status = "OK  " if rep.success else "FAIL"
    ok += rep.success
    print(status, "|", it[:52], "->", rep.output.replace("\n", " ")[:55])
print("{}/{} templates pass".format(ok, len(tests)))
