"""
Paper2 / per-epoch turnover analysis on the ibm_fez continuous-telemetry stream.

Epoch = one distinct calibration version (last_update_date of the device). The
Task-1 scheduler pulls fez every 5 min; consecutive pulls with the same
last_update_date are repeated observations of ONE epoch, so we collapse them to
a single representative snapshot (the latest fetched pull) before computing
adjacent-epoch turnover.

Metrics (all script-computed, committed-data only, zero QPU):
  adjacent-epoch top-3 overlap   |top3(A) intersect top3(B)|  (0..3)
  adjacent-epoch top-10 Jaccard  |top10(A) intersect top10(B)| / union
  best-qubit (argmin C) survival rank@B
  dC distribution                per-qubit readout_total change A->B
  intra-epoch consistency        max |dC| across repeated pulls of one epoch
                                 (QA check: calibration is static within an epoch)

C-quantity follows the paper convention: readout_total, ranked ascending
(best = smallest C).
Output: paper2/results/per_epoch_turnover.json
"""
from __future__ import annotations

import json
import statistics
from datetime import datetime
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAP_DIR = ROOT / "data" / "calib_snapshots" / "ibm_fez"
OUT = ROOT / "paper2" / "results" / "per_epoch_turnover.json"
OUT.parent.mkdir(parents=True, exist_ok=True)


def load(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace(" +", "+").replace(" ", "T"))


def score_map(snap: dict) -> dict:
    return {r["q"]: r["readout_total"] for r in snap["qubits"]}


def best(scores: dict) -> int:
    return min(scores, key=scores.get)


def ranked(scores: dict) -> list:
    return sorted(scores, key=scores.get)


def jacc(a: set, b: set) -> float:
    return len(a & b) / max(len(a | b), 1)


def summarize_dc(dc: list) -> dict:
    if not dc:
        return {"n": 0}
    arr = sorted(dc)
    n = len(arr)
    med = arr[n // 2] if n % 2 else (arr[n // 2 - 1] + arr[n // 2]) / 2
    return {
        "n": n,
        "median": round(med, 5),
        "mean": round(sum(arr) / n, 5),
        "p95": round(arr[int(n * 0.95) - 1], 5),
        "max_abs": round(max(abs(x) for x in arr), 5),
        "pct_gt_0.005": round(100.0 * sum(1 for x in arr if abs(x) > 0.005) / n, 2),
    }


def main():
    files = sorted(SNAP_DIR.glob("2026-*.json"))
    print(f"fez snapshots loaded: {len(files)}")

    by_epoch: dict[str, list] = defaultdict(list)
    for f in files:
        snap = load(f)
        by_epoch[snap["last_update_date"]].append((f, snap))

    epochs = sorted(by_epoch)
    print(f"distinct epochs (calibration versions): {len(epochs)}")

    # Intra-epoch QA: repeated pulls must be calibration-static.
    intra_max_dc = 0.0
    for lu in epochs:
        pulls = by_epoch[lu]
        base = score_map(pulls[0][1])
        for _, snap in pulls[1:]:
            s = score_map(snap)
            for q in set(base) & set(s):
                intra_max_dc = max(intra_max_dc, abs(s[q] - base[q]))
    print(f"intra-epoch max |dC| over repeated pulls: {intra_max_dc:.6f} "
          f"(< 0.001 => calibration static within epoch)")

    # Representative per-epoch snapshot: latest fetched pull.
    reps = {}
    for lu in epochs:
        pull = max(by_epoch[lu], key=lambda p: p[1]["fetched_at"])
        reps[lu] = score_map(pull[1])

    rows = []
    prev_lu = None
    prev_scores = None
    for lu in epochs:
        scores = reps[lu]
        if prev_scores is None:
            prev_lu, prev_scores = lu, scores
            continue
        gap_h = (parse_ts(lu) - parse_ts(prev_lu)).total_seconds() / 3600.0
        both = set(prev_scores) & set(scores)
        t3a = set(ranked(prev_scores)[:3])
        t3b = set(ranked(scores)[:3])
        t10a = set(ranked(prev_scores)[:10])
        t10b = set(ranked(scores)[:10])
        bestA, bestB = best(prev_scores), best(scores)
        rb = {q: i for i, q in enumerate(ranked(scores))}
        dcs = [round(scores[q] - prev_scores[q], 5) for q in both]
        rows.append({
            "epoch_A": prev_lu,
            "epoch_B": lu,
            "gap_hours": round(gap_h, 2),
            "top3_overlap": int(len(t3a & t3b)),
            "top3_jaccard": round(jacc(t3a, t3b), 3),
            "top10_jaccard": round(jacc(t10a, t10b), 3),
            "best_q_A": int(bestA),
            "best_q_B": int(bestB),
            "best_survives": bestA == bestB,
            "best_rank_B": int(rb[bestA] + 1),
            "dC": summarize_dc(dcs),
        })
        prev_lu, prev_scores = lu, scores

    print("\n=== Adjacent-epoch turnover (fez telemetry stream) ===")
    print(f"{'A':<22}{'B':<22}{'gap_h':>6}{'J3':>5}{'J10':>6}{'t3':>4}{'best':>8}{'r@B':>5}")
    for r in rows:
        print(f"{r['epoch_A'][:21]:<22}{r['epoch_B'][:21]:<22}{r['gap_hours']:>6}"
              f"{r['top3_jaccard']:>5}{r['top10_jaccard']:>6}{r['top3_overlap']:>4}"
              f"{str(r['best_q_A'])+'->'+str(r['best_q_B']):>8}{r['best_rank_B']:>5}")

    j3 = [r["top3_jaccard"] for r in rows]
    j10 = [r["top10_jaccard"] for r in rows]
    overlap = [r["top3_overlap"] for r in rows]
    alive = [r["best_survives"] for r in rows]
    med_dc = [r["dC"]["median"] for r in rows]
    maxdc = [r["dC"]["max_abs"] for r in rows]
    print("\n=== Aggregate ===")
    print(f"  pairs={len(rows)}, top-3 Jaccard mean={sum(j3)/max(len(j3),1):.3f} "
          f"median={statistics.median(j3):.3f} min={min(j3):.2f}")
    print(f"  top-10 Jaccard mean={sum(j10)/max(len(j10),1):.3f} "
          f"median={statistics.median(j10):.3f} "
          f"(replication A/B reference was 0.111)")
    print(f"  top-3 full-overlap (3/3) pairs: {sum(1 for o in overlap if o == 3)}/{len(rows)}")
    print(f"  best-qubit survives adjacent epoch: {sum(alive)}/{len(rows)} "
          f"({100.0 * sum(alive) / max(len(rows), 1):.0f}%)")
    print(f"  dC median across pairs: median={statistics.median(med_dc):+.4f}; "
          f"max |dC| across pairs: {max(maxdc):.4f}")

    h = {
        "paper2_per_epoch_turnover": {
            "device": "ibm_fez",
            "snapshot_root": "data/calib_snapshots/ibm_fez",
            "n_snapshots": len(files),
            "n_epochs": len(epochs),
            "epoch_collapse": "latest fetched pull per distinct last_update_date",
            "intra_epoch_max_abs_dc": round(intra_max_dc, 6),
            "score_quantity": "readout_total (ascending = best)",
            "adjacent_pairs": rows,
        },
        "aggregate": {
            "n_pairs": len(rows),
            "top3_jaccard_mean": round(sum(j3) / max(len(j3), 1), 3),
            "top3_jaccard_median": round(statistics.median(j3), 3),
            "top3_jaccard_min": round(min(j3), 3),
            "top10_jaccard_mean": round(sum(j10) / max(len(j10), 1), 3),
            "top10_jaccard_median": round(statistics.median(j10), 3),
            "top3_full_overlap_pairs": int(sum(1 for o in overlap if o == 3)),
            "best_survives_pairs": int(sum(alive)),
            "best_survives_pct": round(100.0 * sum(alive) / max(len(rows), 1), 1),
            "dC_median_median": round(statistics.median(med_dc), 4),
            "dC_max_abs_max": round(max(maxdc), 4),
        },
    }
    with OUT.open("w", encoding="utf-8") as f:
        json.dump(h, f, indent=2, ensure_ascii=False)
    print(f"\nsaved -> {OUT}")


if __name__ == "__main__":
    main()