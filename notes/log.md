# UniMind Execution Log

### 2026-09-01 | Task 1: Crawler refactor + system scheduling
- Added `analysis/fetch_once.py`: single-run fetcher with last_update_date dedup,
  utf-8-sig BOM handling, `.strip()` on JSON keys, 3-attempt exponential backoff,
  one-line summary per device. Verified: dry-run + real fetch; dedup correctly
  skips already-logged calibration timestamps.
- Windows schtasks registered: `UniMind_Fetch_Fez` (every 5 min),
  `UniMind_Fetch_Others` (marrakesh+kingston, every 15 min) — both Ready.
- Added `analysis/schedule_tasks.bat` + `analysis/schedule_tasks_cron.sh` for re-provisioning.
- Committed as [commit].- Committed Task 2: device_identity.py -> notes/device_identity.md (marrakesh operational 156q; fez sibling 156q heavy-hex, 352 edges).
- Committed Task 3: analyze_replication.py -> notes/replication.md (A 08-31 19:56:33 vs B 09-01 08:24:34; J10=0.111, dC_sameq=+0.0010, trigger firing=TRUE via Jaccard<0.5).
- Committed Task 4: stats_upgrade.py -> notes/stats_upgrade.md (70.0 vs 76.7 n=30: Wilson [52.1,83.3]/[59.1,88.2], z=-0.58 p=0.56, MDE ~26pp, TOST(delta=15pp) NOT met).

### 2026-09-02 | Task 5: Manuscript honesty pass (v6 snapshots)
- Created snapshots: paper/tc/versions/v6/{unimind_tc_v6,unimind_tc_compact6_v6}.tex/pdf + paper/unimind_paper_v2.6.tex/pdf (originals untouched).
- Edit (a) Threats to validity: added "Calibration cadence and aliasing" item (TC full/compact6) / new T7 paragraph (v2.6) — snapshots at calibration-cycle cadence, rate-limited refresh, D0-D2 3 cycles ~2d, potential aliasing of weekly/monthly maintenance; 5-min fez telemetry postdates results.
- Edit (b) Device footnote on first ibm_marrakesh mention (TC full Device-and-snapshots; compact6 intro contributions; v2.6 QPU section): verified live 2026-09-01, marrakesh operational 156q so D0-D2 attributable; ibm_fez is a same-gen sibling, not a successor.
- Edit (c) Related work: added Huo & Wei (arXiv:2507.01195, ICCAD 2025) citation + differentiation sentence (average-fidelity vs tail: 2.1x stale-pin, 0.25 top-10 turnover) in TC full/compact6 Related work Placement paragraph and v2.6 Background; added \bibitem{huowei2025} to all three bibliographies.
- Edit (d) pinned-vs-free wording: abstract (TC full/compact6) + E2E sentence now honest — 70.0 vs 76.7 p=0.56, Wilson [52.1,83.3]/[59.1,88.2] overlap, MDE~26pp, TOST(delta=15pp) not conclusive -> claim indistinguishability, never equivalence ("never equivalence" added).
- All three compile clean with pdflatex: TC full 12pp, compact6 7pp, v2.6 41pp; no undefined refs/citations, no LaTeX errors. (a)(c) English text self-drafted, flagged for user review.
- Committed as 9c151f4.

### 2026-09-02 | Task 6: Reproducible public package
- Portability rewrite of `REPRODUCE_TC.sh` / `REPRODUCE_TC.ps1` / `REPRODUCE_v2.5.sh`: path discovery
  via SCRIPT_DIR auto-detect, UNIMIND_ROOT/UNIMIND_PYTHON env overrides, python fallback chain,
  Windows-style paths kept default for git-bash; `REPRODUCE_v2.2.sh` replaced by one-line
  delegation to REPRODUCE_v2.5.sh (was a drifted hardcoded copy).
- Fixes found by running the scripts: ps1 compile step crashed on pdflatex stderr under
  `$ErrorActionPreference=Stop` (now via `cmd /c`); TC.sh step 7 used a stale key
  (`median_alpha` -> `bare_pinned.median.alpha`); transient PDF write-locks on Windows (Defender/
  previewers) handled by `compile_with_retry` in both ps1 and sh.
- Verified locally: REPRODUCE_TC.ps1 9/9 PASSED (TC 12pp, compact6 7pp, 0 overfull);
  REPRODUCE_TC.sh 9/9 PASSED; REPRODUCE_v2.5.sh 6/6 PASSED.
- Added `data/telemetry/`: 5 earliest ibm_fez snapshots (copies) underpinning notes/replication.md
  A/B (08-31 19:56:33 vs 09-01 08:24:34), with provenance README.
- Added root `README.md`: paper table, tracked core claims, reproduce instructions, dependencies,
  data layout, QPU job IDs, lead scripts, verification.
- Secret scan clean: no hardcoded tokens (only `IBM_QUANTUM_TOKEN` env reads in unimind-dev).
- Committed as 311826d.

### 2026-09-02 | Task 7: paper2 per-epoch turnover analysis
- New `paper2/per_epoch_turnover.py` (paper1/ never touched): collapses the 81 ibm_fez 5-min
  telemetry snapshots into 26 epochs by distinct `last_update_date` (calibration version); a
  QA check confirms intra-epoch repeated pulls are calibration-static (max |dC|=0).
- Adjacent-epoch metrics: top-3 overlap, top-3/top-10 Jaccard, best-qubit rank@next epoch,
  ΔC summary (median / p95 / max |ΔC|, %>0.005). Output `paper2/results/per_epoch_turnover.json`.
- Result: turnover is episodic, not gradual - 22/25 adjacent epochs are fully stable
  (top-3 overlap 3/3, best qubit survives), 3/25 fully turn over (J30, J10=0.111, best qubit
  displaced to ranks 18-54); median J10=1.0, mean J3=0.88/mean J10=0.893; max |ΔC|=0.9709.
  Supports the "reuse breaks at day scale, stable intra-day" narrative.
- Committed as 12b58e8.
