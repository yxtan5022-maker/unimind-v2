# UniMind Experiment Log

Protocol (Phase 0.2 / Phase 6): every experiment records ID, date, commit,
hardware, backend, parameters, seeds, shots, raw data path, processed data
path, figures, and conclusion. New experiments MUST be appended here with a
new E-ID before results enter the paper. All experiments fork from the
v2.0-freeze tag.

---

## E-01 | LLM reliability benchmark (v1.7 frozen protocol)
- **Date**: 2026-08-14 (frozen v1.7 submission)
- **Commit**: unimind-dev @ 6f21bc0
- **Hardware**: consumer laptop (mock LLM, no API)
- **Backend**: in-process mock; Unibit simulator backend
- **Parameters**: 50 valid + 10 adversarial tasks per quality level, q ∈ {1.0, 0.9, 0.7, 0.5}, fail-rate f_r = 0.1
- **Seeds**: single seed 42 (limitation → addressed by E-04)
- **Raw data**: `data/raw/llm_reliability_mock_q*.json`
- **Processed**: v1.7 paper Table tab:reliability
- **Figure**: v1.7 fig:reliability
- **Conclusion**: end-to-end success 100%→94% as q degrades; adversarial rejection 100%. Single-seed estimate; refined by E-04.

## E-02 | Physical QPU validation, free placement (v1.7)
- **Date**: 2026-08-14
- **Commit**: unimind-dev @ 6f21bc0
- **Hardware**: IBM Quantum open plan
- **Backend**: ibm_marrakesh (156q), Sampler V2, opt level 1, NO initial_layout
- **Parameters**: weights {0.1,...,0.9}; bare vs readout twirling (16 randomizations); 8192 shots
- **Seeds**: transpile seed 42
- **Raw data**: `data/raw/qpu_validation_real.json`, `data/raw/qpu_validation_real_mitigated.json`
- **Processed**: v2.0 §5.10 intro + tab:placement row "v1.7"
- **Conclusion**: max dev 0.392 bare / 0.245 twirled — later shown by E-05 to be placement artifact.

## E-03 | Architectural ablation (quality + narrow-template stress)
- **Date**: 2026-08-23
- **Commit**: this repo, v2.0-freeze tag (`analysis/ablation_study.py --part quality|stress`)
- **Hardware**: laptop, mock LLM
- **Parameters**: 150 valid tasks × 3 seeds × {S0,S1,S2,S3} × q ∈ {0.5,0.7,0.9}; stress: q=0.7, f_r ∈ {0.3,0.5}
- **Seeds**: 42/43/44
- **Raw data**: `analysis/results/ablation_quality.json`, `ablation_stress.json`
- **Figure**: `paper/figures/fig_ablation.pdf` panel (a) + S3 curve of (b)
- **Conclusion**: validation adds zero success delta (fail-fast only); self-healing is load-bearing (+34pp @q=0.5); narrow fallback bounded by template coverage.

## E-04 | Instrumented failure taxonomy + multi-seed reliability
- **Date**: 2026-08-23
- **Commit**: v2.0-freeze (`analysis/reliability_instrumented.py`, `failure_taxonomy.py`)
- **Hardware**: laptop, mock LLM
- **Parameters**: 200 tasks/run × 9 configs (q ∈ {0.5,0.7,0.9} × 3 seeds), call-level logging of every generation/heal call
- **Seeds**: 42/43/44
- **Raw data**: `analysis/results/reliability_instrumented.json` (paths per run)
- **Processed**: `analysis/results/failure_taxonomy.{json,md}`
- **Figure**: `paper/figures/fig_failure_taxonomy.pdf`
- **Conclusion**: 353 injected faults; recovery uniform across corruption classes (82.5–87.7%, Wilson CIs overlap); q=0.5 success 91.7% [89.2,93.6] refines v1.7's 94%.

## E-05 | Placement-controlled QPU sweep (2×2 design) ← core of RQ2/RQ3
- **Date**: 2026-08-23
- **Commit**: v2.0-freeze (`analysis/qpu_sweep.py`, `local_noise_sim.py`, `sweep_analysis.py`)
- **Hardware**: IBM Quantum open plan
- **Backend**: ibm_marrakesh; calibration snapshot last_update 2026-08-22 22:18:51+08:00
- **Parameters**: w ∈ {0.05..0.95} step 0.05 (19 pts), 8192 shots, pinned via initial_layout; cells: q98 bare/twirled × 3 repeat jobs, q37 (adversarial, readout err 82%) bare/twirled, unpinned default ×1
- **Job IDs**: da57ecu1vhnc73flo4qg, da57fjjotlns739bj5r0, da57g3maa69c739khdpg (q98 bare r0–r2); da57hru1vhnc73flo8ug, da57j143jnrc73agv900 (q98 twirl r1–r2); da57mqjotlns739bjd3g (q37 bare); da57nl43jnrc73agvdjg (q37 twirl)
- **Raw data**: `data/qpu_sweep/sweep_{bare,twirled}_r{0..4}.json` (each embeds job_id + calibration top5)
- **Provenance snapshot**: `analysis/results/calib_provenance.json` (same calibration timestamp as jobs)
- **Processed**: `analysis/results/sweep_analysis.json`
- **Figures**: `fig_qpu_placement_2x2.pdf`, `fig_noise_vs_qpu.pdf`
- **Conclusion**: placement-dominated fidelity. q98 bare max dev 0.028 [0.020–0.029] passes 0.05 tolerance; q37 fails at 0.213 (twirl 0.144); affine P_obs=b+a·w fits all cells at shot-noise level; noise-model/QPU median ratio 1.4× on good qubit. Withdraws v1.7 headline claim.

## E-06 | Full-coverage fallback stress (S3X)
- **Date**: 2026-08-23
- **Commit**: v2.0-freeze (`analysis/ablation_study.py --part stress2`)
- **Parameters**: S2 vs S3X (rule coverage extended to all 9 intent classes), q=0.7, f_r ∈ {0.3,0.5}, 150 tasks × 3 seeds
- **Seeds**: 42/43/44
- **Raw data**: `analysis/results/ablation_stress2.json`
- **Conclusion**: S3X reaches 100% at both levels; 79/79 unavailability events recovered by deterministic layer. Fallback value is real but coverage-limited.

## E-07 | Local calibration noise model comparison
- **Date**: 2026-08-23
- **Commit**: v2.0-freeze (`analysis/local_noise_sim.py`)
- **Backend**: AerSimulator + NoiseModel.from_backend(ibm_marrakesh), identical pinned circuits as E-05
- **Raw data**: `data/qpu_sweep/sweep_localnoise.json`
- **Conclusion**: noise model explains most good-qubit error (median E_QPU/E_noise = 1.4×); residual attributed to coherent drift between snapshot and execution.
