# UniMind

Middleware for calibration-aware scheduling and placement of classical-AI + quantum workloads.
Every quantitative claim in the papers traces to a recorded QPU job or committed snapshot.

## Papers

The active manuscript lives as two IEEEtran-formatted TC papers plus the standalone full
report, all with milestone-versioned snapshots under `paper/tc/versions/`:

| paper | file | pages | status |
|---|---|---|---|
| TC full | `paper/tc/versions/v8/unimind_tc_v8.pdf` | 12 | **current (v8, TC submit-ready, D3 + 337 hourly)** |
| TC compact (CAL submission) | `paper/tc/versions/v7/unimind_tc_compact6_v7.pdf` | 7 | snapshot (v7) |
| Full technical report | `paper/unimind_paper_v2.6.pdf` | 41 | snapshot |

> **Active v8:** `paper/tc/unimind_tc.tex` / `paper/tc/unimind_tc.pdf` (12p, IEEEtran) is the v8 working copy submitted to TC as `unimind_tc_v8` (`v8.0-data-release`, 2026-09-03). Frozen to `paper/tc/versions/v8/`.

Working copies (`paper/tc/unimind_tc.tex`, `paper/tc/unimind_tc_compact6.tex`,
`paper/unimind_paper_v2.5.tex`) are the in-progress sources; `versions/vN/` is an immutable
archive. See `paper/tc/versions/README.md` for the milestone table.

## Core claims (all traced)

1. **Temporal validity**: day-over-day drift ρ=0.567–0.579, τ=0.42–0.43, top-10 Jaccard 0.11–0.25 across all 6 D0–D3 pairs; stale top-3 is 1.94–2.1× worse fresh (24–34 h QPU-anchored; 1.45–2.55× across D0–D3). Hourly margins M₃~10⁻³ vs. median |ΔC|=0.0127 explain turnover while intra-epoch S(t)=1.0 to 15 h (0/71 triggers, 337 snapshots/71 epochs, 3 backends).
2. **Adaptive refresh**: Jaccard<0.5 / ΔC>0.005 trigger at ~0.04 ms/score; 144-threshold sweep at Pareto knee (periodic-6h fires 5×, 48h misses).
3. **Refresh dominates placement**: fresh pins lift both arms +33/37 pp on 6-qubit suite; pinned vs. free indistinguishable at n=30/arm (70.0 vs. 76.7 %, p=0.56, Wilson [52.1,83.3]/[59.1,88.2], MDE≈32 pp at 80% power, bounded null).

## Reproduce

No IBM quota is needed for most claims — every number traces to committed data.

- Windows PowerShell: `powershell -ExecutionPolicy Bypass -File REPRODUCE_TC.ps1`
- git-bash / Linux: `bash REPRODUCE_TC.sh` (TC papers) or `bash REPRODUCE_v2.5.sh` (v2.5 report)

### Dependencies

Python ≥ 3.10 with `numpy`, `scipy`, `matplotlib`, `pytest`, plus Qiskit stack
(`qiskit`, `qiskit-aer`, `qiskit-ibm-runtime`). Hardware steps additionally require an IBM
Quantum token exported as `IBM_QUANTUM_TOKEN` (read from env only, never stored on disk).

## Data layout

| path | contents |
|---|---|
| `data/drift/calib_2026-{08-29,08-30,08-31,09-01,09-02}.json` | D0 / D1 / D2 / D3 / D4 processed snapshots (marrakesh, D0–D2 QPU-anchored) |
| `data/calib_snapshots/ibm_marrakesh/` | 111 raw hourly snapshots (156-qubit, 2026-08-31 to 09-03) |
| `data/calib_snapshots/ibm_fez/` | 117 raw 5-min telemetry pulls (2026-08-31 to 09-03) |
| `data/calib_snapshots/ibm_kingston/` | 109 raw 15-min telemetry pulls (2026-08-31 to 09-03) |
| `data/calib_snapshots/telemetry_log.jsonl` | 337 total / 328 in Kaplan-Meier, 71 epochs, 3 backends |
| `analysis/results/survival_analysis.json` | KM survival S(t)=1.0 to 15 h, 0/71 triggers |
| `data/telemetry/` | curated telemetry evidence (replication A/B snapshots) |
| `data/e2e/e2e_angle_{full,ablated}*.json` | E2E placements batches (frozen + refresh) |
| `data/jgpu/j_real*.json` | real J(G) labels, k=9–18 |
| `analysis/results/*.json` | all processed analysis outputs |
| `paper2/results/per_epoch_turnover.json` | fez per-epoch turnover analysis (paper 2) |

## Key QPU job IDs

| job | role |
|---|---|
| `daadeocjbipc73ffq83g` | refresh-full E2E |
| `daadeosjbipc73ffq840` | refresh-ablated E2E |
| `daadgmmrbfbs73cijmbg` | refresh-pinned J(G) real labels |
| `daad3mse74ec73akmpi0` | frozen E2E angle full (08-31) |
| `daad3n6rbfbs73cij840` | frozen E2E angle ablated (08-31) |
| `daad3r9qtnsc73d2h7kg` | real-QPU J(G) labels (k=9–18) |
| `da9etepqtnsc73d1gv4g` / `da9eslpqtnsc73d1gudg` | frozen composition full / ablated |

Full registry (incl. E-05/E-08 sweep cells) in `EXPERIMENTS.md`.

## Reproducibility lead scripts

| script | output |
|---|---|
| `analysis/device_identity.py` | notes/device_identity.md (fleet status) |
| `analysis/analyze_replication.py` | notes/replication.md (fez A/B check) |
| `analysis/stats_upgrade.py` | notes/stats_upgrade.md (CI / z-test / MDE / TOST) |
| `analysis/drift_analysis.py` | results/drift_analysis.json |
| `analysis/refresh_policy_sweep.py` | results/refresh_policy_analysis.json |
| `analysis/power_analysis.py` | results/power_analysis.json |
| `analysis/jg_failure_analysis.py` | results/jg_failure_analysis.json |
| `analysis/reliability_model.py` | results/reliability_model.json |
| `analysis/hw_batch_analysis.py` | deterministic batch summaries |
| `analysis/fetch_once.py` | single-run telemetry fetcher (Task-1 scheduler) |

## Paper 2 (per-epoch telemetry)

`paper2/per_epoch_turnover.py` collapses the ibm_fez 5-min telemetry stream into epochs
(distinct calibration versions) and reports adjacent-epoch top-3 overlap, top-10 Jaccard,
and the ΔC distribution. Run `python paper2/per_epoch_turnover.py`.

## Verification

- `tests/test_unibit_correctness_v2_2.py` — regression on Algorithm 1 (pure R_y).
- `analysis/test_unibit_math.py` — 13/13 mathematical propositions.
- `python -m pytest tests/ analysis/test_unibit_math.py -q`

## Notes / memory

`notes/` holds the round-by-round evidence (device identity, replication, stats). `GATES.md`,
`MEMORY.md`, `RESEARCH_QUESTIONS.md`, `EXPERIMENTS.md` are the project logbook. See
`docs/` for the UniBit math, reliability model, and routing-SOTA notes.