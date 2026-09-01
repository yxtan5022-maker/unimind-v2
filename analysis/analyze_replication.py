"""Task 3: Cross-device replication check for the continuous-telemetry story.

Compares two ibm_fez calibration snapshots:
  - 2026-08-31 19:56:33+08:00   (last_update of data/calib_snapshots/ibm_fez/2026-08-31T125233.397116+0000.json)
  - 2026-09-01 08:24:34+08:00   (last_update of data/calib_snapshots/ibm_fez/2026-09-01T010557.459596+0000.json)

Metrics (script-computed, we do NOT trust hand values):
  top-10 Jaccard          rank turnover of best-qubit set
  delta_C(best qubit)     readout error change of the argmin C(q) qubit
  trigger firing          Jaccard < 0.5 OR |dC(best)| > 0.005

Output: notes/replication.md
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import math

ROOT = Path(r"C:\Users\SCSM11\Desktop\unimind-v2")
SNAP_DIR = ROOT / "data" / "calib_snapshots" / "ibm_fez"
OUT = ROOT / "notes" / "replication.md"
OUT.parent.mkdir(parents=True, exist_ok=True)

A = SNAP_DIR / "2026-08-31T125233.397116+0000.json"   # last_update 2026-08-31 19:56:33+08:00
B = SNAP_DIR / "2026-09-01T010557.459596+0000.json"   # last_update 2026-09-01 08:24:34+08:00


def load(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def rank(snap: dict):
    rows = sorted(snap["qubits"], key=lambda r: r["readout_total"])
    return rows, [r["q"] for r in rows]  # sorted rows + q order


def jacc(sa: list, sb: list, k: int = 10) -> float:
    a = set(sa[:k]); b = set(sb[:k])
    return len(a & b) / max(len(a | b), 1)


def main():
    snapA = load(A)
    snapB = load(B)

    rowsA, orderA = rank(snapA)
    rowsB, orderB = rank(snapB)

    # C-quantity of interest: readout_total error of each qubit.
    cA = {r["q"]: r["readout_total"] for r in rowsA}
    cB = {r["q"]: r["readout_total"] for r in rowsB}

    # best qubit in each snapshot by C(q)
    bestA = rowsA[0]["q"]
    bestB = rowsB[0]["q"]
    c_best_A = rowsA[0]["readout_total"]
    c_best_B = rowsB[0]["readout_total"]
    delta_c_best = c_best_B - c_best_A

    # best qubit consistency: same qubit? then delta is meaningful; if changed,
    # also report the SAME qubit's readout drift too.
    if bestA == bestB:
        delta_same_qubit = delta_c_best
    else:
        delta_same_qubit = cB.get(bestA) - cA.get(bestA)

    j1 = jacc(orderA, orderB, 1)
    j3 = jacc(orderA, orderB, 3)
    j10 = jacc(orderA, orderB, 10)

    # trigger definition (per paper / task spec)
    trigger_jacc = j10 < 0.5
    trigger_dc = abs(delta_c_best) > 0.005
    firing = trigger_jacc or trigger_dc

    lines = []
    lines.append("# Replication check: ibm_fez snapshot pair")
    lines.append("")
    lines.append(f"Script: `analysis/analyze_replication.py` (all numbers below computed by it)")
    lines.append("")
    lines.append("| item | value |")
    lines.append("|---|---|")
    lines.append(f"| snapshot A (last_update) | {snapA['last_update_date']} |")
    lines.append(f"| snapshot B (last_update) | {snapB['last_update_date']} |")
    lines.append(f"| gap (B - A) hours | {round((__import__('datetime').datetime.fromisoformat(snapB['last_update_date'].replace(' +','+').replace(' ','T')) - __import__('datetime').datetime.fromisoformat(snapA['last_update_date'].replace(' +','+').replace(' ','T'))).total_seconds()/3600, 2)} |")
    lines.append(f"| top-1 overlap | {j1:.3f} |")
    lines.append(f"| top-3 overlap | {j3:.3f} |")
    lines.append(f"| top-10 Jaccard | {j10:.3f} |")
    lines.append("")
    lines.append("### Best-qubit (argmin C(q)) drift")
    lines.append("")
    lines.append("| item | A | B | delta |")
    lines.append("|---|---|---|---|")
    lines.append(f"| best qubit | {bestA} | {bestB} | {'same' if bestA==bestB else 'CHANGED'} |")
    lines.append(f"| C(best qubit) | {c_best_A:.5f} | {c_best_B:.5f} | {delta_c_best:+.5f} |")
    lines.append(f"| dC(same qubit {bestA}) (if changed) | - | - | {delta_same_qubit:+.5f} |")
    lines.append("")
    lines.append("### Trigger status")
    lines.append("")
    lines.append(f"- Jaccard<0.5 firing? **{trigger_jacc}**  (J10={j10:.3f})")
    lines.append(f"- dC(best)>0.005 firing? **{trigger_dc}**  (dC={delta_c_best:+.5f})")
    lines.append(f"- **Trigger FIRING = {firing}**")
    lines.append("")

    # standard quantitative detail
    lines.append("## Appendix: full top-10 comparison")
    lines.append("")
    lines.append(f"A top-10: {orderA[:10]}")
    lines.append(f"B top-10: {orderB[:10]}")
    lines.append("")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUT)
    print(OUT.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()