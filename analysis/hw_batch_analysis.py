"""Deterministic summary of the 2026-08-31 hardware batches.

Inputs (produced by e2e_angle_batch.py / j_real_labels.py collect):
  data/e2e/e2e_angle_full.json, e2e_angle_ablated.json   (30 angle circuits/arm)
  data/jgpu/j_real.json                                  (k=9..18 real labels)
Reference snapshots: data/drift/calib_2026-08-29.json (D0, the pin source),
                     data/drift/calib_2026-08-30.json (D1).

Outputs analysis/results/hw_batch_analysis.json with:
  - e2e placement: pass/arm + Wilson CI + worst-qubit-per-failing-circuit
    attribution vs D0/D1 C(q);
  - J(G) real labels: per-k max_dev, pass, and, per circuit, the placed
    qubit carrying the largest per-bit deviation with its D0/D1 C and rank.
"""
from __future__ import annotations

import json
import math
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RES = ROOT / "analysis" / "results"


def wilson(k, n, z=1.96):
    if n == 0:
        return [None, None]
    p = k / n
    den = 1 + z * z / n
    c = p + z * z / (2 * n)
    s = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [100 * (c - s) / den, 100 * (c + s) / den]


def qubit_C(snaps, q):
    return {d: {r["q"]: r["readout_total"] for r in snaps[d]["qubits"]}.get(q)
            for d in snaps}


def main():
    d0 = json.loads((DATA / "drift" / "calib_2026-08-29.json").read_text(encoding="utf-8"))
    d1 = json.loads((DATA / "drift" / "calib_2026-08-30.json").read_text(encoding="utf-8"))
    c0 = {r["q"]: r["readout_total"] for r in d0["qubits"]}
    c1 = {r["q"]: r["readout_total"] for r in d1["qubits"]}
    rank0 = {q: i + 1 for i, q in enumerate(sorted(c0, key=lambda q: c0[q]))}
    rank1 = {q: i + 1 for i, q in enumerate(sorted(c1, key=lambda q: c1[q]))}

    out = {"date": "2026-08-31", "device": "ibm_marrakesh",
           "shots": 4096, "tol": 0.05}

    # ---------------- E2E placement batch ----------------
    arms = {}
    for arm in ("full", "ablated"):
        f = json.loads((DATA / "e2e" / "e2e_angle_{}.json".format(arm)).read_text())
        hw = f["hardware"]
        pw = sum(1 for h in hw if h["hw_pass"])
        n = len(hw)
        fails = []
        for h in hw:
            if not h["hw_pass"]:
                devs = h["per_bit_dev"]
                idx = max(range(len(devs)), key=lambda i: devs[i])
                fails.append({"placed_qubit": h["placed_qubits"][idx],
                              "max_dev": devs[idx],
                              "per_bit_dev": devs, "placed": h["placed_qubits"]})
        arms[arm] = {"pass": pw, "n": n, "pct": round(100 * pw / n, 1),
                     "wilson": [round(x, 1) for x in wilson(pw, n)],
                     "n_failed_bits_gt_tol": sum(
                         1 for h in hw for d in h["per_bit_dev"] if d > 0.05),
                     "worst_failing_qubits_D0C":
                         sorted(Counter(x["placed_qubit"] for x in fails).items(),
                                key=lambda kv: -kv[1])[:8],
                     "sampled_worst_fail":
                         [{"qubit": x["placed_qubit"], "C_D0": c0.get(x["placed_qubit"]),
                           "C_D1": c1.get(x["placed_qubit"]),
                           "rank_D0": rank0.get(x["placed_qubit"])}
                          for x in fails[:5]]}
    out["e2e_angle"] = {"snapshot_for_pins": "calib_2026-08-29.json",
                        "arms": arms}

    # ---------------- J(G) real labels ----------------
    jr = json.loads((DATA / "jgpu" / "j_real.json").read_text())
    rows = []
    per_k = {}
    ser = []
    for r in jr["rows"]:
        devs = r["per_bit_dev"]
        idx = max(range(len(devs)), key=lambda i: devs[i])
        q = r["placed_qubits"][idx]
        rows.append({"k": r["k"], "pattern": r["pattern"], "max_dev": r["max_dev"],
                     "pass": r["pass_05"], "worst_qubit": q,
                     "C_D0": c0.get(q), "C_D1": c1.get(q),
                     "rank_D0": rank0.get(q), "rank_D1": rank1.get(q)})
        per_k.setdefault(r["k"], []).append(r["max_dev"])
        ser.append((len(r["placed_qubits"]), r["max_dev"]))
    ks = sorted(per_k)
    out["j_real"] = {
        "k_range": [ks[0], ks[-1]], "n": len(rows),
        "pass": sum(1 for r in rows if r["pass"]), "n_circuits": len(rows),
        "per_k_max_dev_mean": {k: round(sum(per_k[k]) / len(per_k[k]), 4)
                               for k in ks},
        "per_k_rows": rows,
        "n_pass_as_written": sum(1 for r in rows if r["pass"]),
        "misses_late_chain_only": sum(1 for r in rows if r["k"] >= 11
                                      and r["worst_qubit"] in (37, 45, 46, 47, 57)),
    }
    # spearman k vs max_dev across rows
    from scipy import stats
    sr = stats.spearmanr([r["k"] for r in rows], [r["max_dev"] for r in rows])
    out["j_real"]["spearman_k_vs_maxdev"] = round(float(sr.correlation), 4)
    out["j_real"]["spearman_p"] = round(float(sr.pvalue), 4)
    # C(worst qubit) vs its per-bit dev (pooled bit-level across circuits)
    pooled = []
    for r in jr["rows"]:
        for i, d in enumerate(r["per_bit_dev"]):
            q = r["placed_qubits"][i]
            pooled.append((d, c0.get(q)))
    ps = stats.spearmanr([x[1] for x in pooled], [x[0] for x in pooled],
                         nan_policy="omit")
    out["j_real"]["spearman_C_vs_bitdev"] = round(float(ps.correlation), 4)

    (RES / "hw_batch_analysis.json").write_text(
        json.dumps(out, indent=1, ensure_ascii=False))

    print("== E-09b placement (n=30/arm) ==")
    for arm in ("full", "ablated"):
        a = arms[arm]
        print("  {} pass {}/{} = {}% CI {}".format(arm, a["pass"], a["n"],
              a["pct"], a["wilson"]))
        print("    worst failing qubits (D0 C):", a["worst_failing_qubits_D0C"][:5])
    print("== J(G) real labels ==")
    print("  pass {}/14; k~max_dev mean:", {k: out['j_real']['per_k_max_dev_mean'][k]
          for k in ks})
    print("  spearman k vs max_dev = {} (p={})".format(
        out["j_real"]["spearman_k_vs_maxdev"], out["j_real"]["spearman_p"]))
    print("  spearman C(worst) vs bit-dev =", out["j_real"]["spearman_C_vs_bitdev"])
    print("written ->", RES / "hw_batch_analysis.json")


if __name__ == "__main__":
    main()