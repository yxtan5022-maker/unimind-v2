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

## E-08 | Hardware-aware routing: C(q) score + stratified QPU validation (RQ3)
- **Date**: 2026-08-23
- **Pre-registered before running.** Script: `analysis/hw_router.py` (--part local/qpu/analyze)
- **C(q) definition**: primary = total readout assignment error p01+p10 (justified by E-05: readout dominates single-qubit encoding distortion); tiebreak -min(T1,T2). Transparent monotone variant of charter formula; no weights fitted on anchors (n=2 would overfit).
- **Design**: full 156-qubit calibration snapshot -> ranking -> anchor check (q98 top, q37 bottom, consistency vs E-05 recorded 0.004395/0.821777) -> stratified mini-sweep: 6 qubits at ranks {best, p25, p50, p75, p95} + q37 anchor, bare 19-weight grid, pinned, 8192 shots, 1 job each -> max_dev & affine (a,b) vs C(q); Spearman rank corr (exact perm n=6); overhead microbench (selector ms, transpile pinned vs free).
- **Success**: H3.2 top-1 passes 0.05 tolerance & bottom fails; H3.1 all upper-half qubits >=90% weights pass; H3.3 selector+transpile overhead << queue/execution time.
- **Raw data**: `analysis/results/calib_full_e08.json`, `data/qpu_sweep/router_sweep_q*.json`
- **Job IDs**: da5c21eaa69c739kmk4g (q98), da5c2es3jnrc73ah4dn0 (q20), da5c2seaa69c739kmksg (q105), da5c39jotlns739bofp0 (q31), da5c3n43jnrc73ah4eu0 (q119), da5c44e1vhnc73flthu0 (q37)
- **Figure**: `paper/figures/fig_router.pdf`
- **Conclusion**: ALL THREE HYPOTHESES PASS. max_dev strictly monotone along C(q) rank: 0.020/0.038/0.0496/0.0516/0.197/0.304 (best→worst); Spearman rho=1.000, exact p=0.0028 (n=6). Tolerance boundary between p50 and p75. Affine slope degrades monotonically 0.989→0.771, offset +0.005→+0.173 — consistent with RQ2 readout mechanism. Overhead: selector 0.036 ms, pinned transpile 1.9 ms, aware 3-qubit layout 0.294 ms. Docs: `docs/hw_routing.md`.

## E-09 | End-to-end chain composition on real hardware (RQ5)
- **Date**: 2026-08-23
- **Pre-registered before running.** Script: `analysis/e2e_chain.py`
- **Design**: 36 NL tasks = 9 intent classes x 4 reps, mock LLM q=0.7 f_r=0.1 (same seeds both arms, paired); arms: FULL = validation+heal+full-coverage fallback + hardware-aware placement (pin argmin-C(q) qubit(s)); ABLATED = validation-only + default free placement (v1.7 behaviour). Quantum-task circuits accumulated and submitted as ONE batched job per arm (4096 shots), ibm_marrakesh.
- **Metrics**: P_E2E per arm (Wilson CI, paired diff), latency breakdown, recovery-path matrix, per-weight E_Z tolerance pass rate (FULL arm, H5.3 >=90%), bell/ghz parity deviation reported separately.
- **Mock-vs-real boundary**: LLM stage is mock (documented); every later stage (sandbox exec, transpile, QPU) real.
- **Raw data**: `data/e2e/e2e_{full,ablated}.json` (+ `*_pending.json` with job ids)
- **Job IDs**: full da5c8kuaa69c739kmr40 (QUEUED), ablated da5d6du1vhnc73fluoqg (QUEUED) — open-plan usage limit met; collect via `python analysis/e2e_chain.py --stage collect` when quota resets (idempotent).
- **Orchestration-stage result (already final)**: FULL arm 54/54 success (46 first_pass + 8 healed) = 100%; ABLATED 47/54 = 87.0% (7 FAIL_NO_LLM/EXEC_FAILED) — Wilson CIs separated. Quantum PUBs: 18 (full) + 17 (ablated). A-01 model cross-check: S3X pred 97.3% vs obs 100%; healed count 8 vs pred ~10.5 ✓.
- **Conclusion**: hardware fidelity scoring pending quota; software-path gain already measured.

## A-01 | Reliability absorbing-chain model vs. logged data (RQ4)
- **Date**: 2026-08-23
- **Type**: analysis of existing E-03/E-06 data (no new runs)
- **Script**: `analysis/reliability_model.py` → `analysis/results/reliability_model.json`
- **Model**: exact iid path probabilities (None-abort truncation, broken-slot consumption, H=4 heal budget, mock clipping rule); narrow-fallback coverage c=2/9 derived from quote-injection SyntaxError mechanism
- **Result**: 23/23 cells PASS (predictions inside Wilson 95% CI). Naive-independence gap at q=0.5 is 12.3pp but structural-exact residual is +0.3pp; q=0.7 residual +4.0pp (in CI). "Correlation penalty" interpretation of §5.13 falsified — the gap is retry-budget truncation.
- **Intervention ranking** (ρ_h @q0.5): None-as-wasted-slot +12.6pp > healer quality 0.9 (+8.8pp) > budget doubling (+2.1pp).
- **Docs**: `docs/reliability_model.md`

## A-02 | Unibit mathematics verification + paper-figure audit (RQ1)
- **Date**: 2026-08-23
- **Type**: property-based numerical verification against implementation
- **Script**: `analysis/test_unibit_math.py` (13/13 pass) → `unibit_math.json`; corrected figure data `unibit_fig_data.json`
- **Findings**: (1) collapse ≡ position-adaptive threshold T_i=τ/g_i, structural dead zone beyond sinc root x*=1.3918 (~56% of tail positions cannot pass at default τ); (2) repo multi-bit fold applies X-then-Ry for b_i=1 → P(1)=1−w_i, diverging from the paper's stated identity (pure-Ry branch verified exact); (3) fig:unibit panel (b) coordinates are fabricated (negative tail impossible under Eq.(3); real s_1=0.7254>τ ⇒ collapse[1]=1, not all-zero). Panel (a) correct.
- **Docs**: `docs/unibit_math.md` (three v2.1 corrections proposed)
