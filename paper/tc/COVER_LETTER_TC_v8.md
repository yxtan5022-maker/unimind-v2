# Cover Letter — IEEE Transactions on Computers (Regular Paper, Measurement Study)

**To the Editor-in-Chief and Associate Editor, IEEE Transactions on Computers**

Dear Editors,

We submit the manuscript **“UniMind: Calibration-Aware Scheduling and Placement for Quantum-Accelerated AI Middleware”** (12 pages, IEEEtran, `unimind_tc_v8`, `v8.0-data-release`) for consideration as a Regular Paper — Measurement Study in *IEEE Transactions on Computers*.

**What the paper is (and is not).** This is a measurement study, not a claim of quantum advantage or a new quantum algorithm. We instrument a 156-qubit superconducting device (`ibm_marrakesh`, heavy-hex, 176 couplers) with four daily snapshots (D0--D3, 2026-08-29 to 09-01; D0--D2 QPU-anchored, D3 calibration-only, 6 inter-day pairs) and 337 hourly calibration-only snapshots from 71 calibration epochs across three backends (2026-08-31 to 09-02) to bound a new systems primitive: the **Calibration Validity Horizon $T_{\mathrm{valid}}$**. We build **UniMind**, a user-space, multi-backend middleware (Qiskit/Aer, CUDA-Q, IBM Quantum) that scores (`C(q)=p_{01}+p_{10}`), places (connected chain / 7-dim $J(G)$), transpiles, executes and refreshes calibration data in a closed loop.

**Why TC.** The contribution is systems: scheduling under non-stationary calibration data, staleness as an operational-policy failure ($\sim0.04$ ms scoring), and a working adaptive refresh trigger at the Pareto knee of 144 threshold combos. Comparison class is not “beats vendor plumbing” but “a scored `initial_layout` whose age is policed beats the same score whose age is not” — the controlled $n=30$/arm E2E experiment of §7. A companion reliability calculus for the separable LLM-orchestration path is included as Appendix D so the scheduling core can be evaluated independently.

**Four findings (all traced, v8 extends v7 with 4th daily D3 + 337 hourly snapshots):**

1. **Bounded, small $T_{\mathrm{valid}}$:** day-over-day $\rho{=}0.567$--$0.579$, $\tau{=}0.42$--$0.43$, top-10 Jaccard $0.11$--$0.25$ across all 6 D0--D3 pairs; stale top-3 is $1.94$--$2.1\times$ worse fresh (24--34 h, QPU-anchored; $1.45$--$2.55\times$ across D0--D3 calibration matrix); hourly margins $M_3\sim10^{-3}$ vs. median $|\Delta C|=0.0127$ explain daily turnover while intra-epoch hourly stability is perfect (0/71 epochs fire, $S(t){=}1.0$ to 15~h, 337 snapshots, 3 backends). $T_{\mathrm{valid}}\gtrsim15$ h intra-epoch, $\lesssim24$ h inter-day (lower bound at $k{=}6$).
2. **Adaptive refresh dominates static/periodic at near-zero cost and zero hourly false positives:** trigger “top-10 Jaccard $<0.5$ or $\Delta C>0.005$” fires on every inter-day transition and on D0→D1 to restore $+33$ pp (Fisher $p=0.019$, $70.0\%$ vs. $36.7\%$), while periodic-$6$h fires $5\times$ and hourly $S(t){=}1.0$ shows $0\%$ false positives. 144-threshold sweep isolates the miss region ($\tau_J<0.25 \land \tau_C>0.0056$).
3. **Bounded null at $k=6$:** refreshed pinned vs. free is indistinguishable with the present power ($70.0\%$ [52.1,83.3] vs. $76.7\%$ [59.1,88.2], Fisher $p=0.77$, Wilson 95% CI, MDE $\approx32$ pp at 80% power); we report a bounded null, not equivalence. Placement is decisive at extremes (`q98` $0.028$ vs. `q37` $0.213$) and sets the floor at $k\ge9$ under stale pins.
4. **Proxy models do not transfer:** $J(G)$ size-out-of-sample $\rho$ collapses $0.818\to0.13$ ($p=0.36$) when real QPU labels replace simulator proxy; feature ablation + variance crossover at $k\approx100$--$128$ close the mechanism loop. Full weights, ablations and variance tables are in the repo.

**Reproducibility (the paper’s backbone).** Every number traces to a QPU job ID (`daadeocjbipc73ffq83g` refresh-full E2E, `daadeosjbipc73ffq840` refresh-ablated E2E, `daadgmmrbfbs73cijmbg` $J(G)$ real labels, etc.) or calibration JSON (`data/drift/calib_2026-08-*.json` + `calib_2026-09-01.json` + `data/calib_snapshots/` 337 hourly, 71 epochs). Analysis code (`analysis/*.py`, `analysis/results/*.json` including `survival_analysis.json`) reproduces all tables without IBM quota: `REPRODUCE_TC.ps1` / `REPRODUCE_TC.sh`. Data are CC-BY-4.0, code MIT (`LICENSE` / `data/LICENSE_DATA.md`). GitHub: `https://github.com/yxtan5022-maker/unimind-v2` Tag `v8.0-data-release` (pending Zenodo DOI `10.5281/zenodo.XXXXXXX`, to be updated after Zenodo reserve; `.zenodo.json` + `CITATION.cff` included).

**Disclosures.**

- *Prior publication:* This work has not been published elsewhere and is not under review at any other venue. A GitHub-hosted technical report and repo (`unimind-v2`) are preprints per IEEE policy and do not constitute prior publication. If an arXiv preprint is posted (`cs.ET`/`cs.SE` + `quant-ph`), we will update the submission with the ID. The compact 6-page version (`unimind_tc_compact6_v7`) is held as a backup and will not be submitted elsewhere during TC review.
- *AI assistance (IEEE disclosure):* Generative AI (Muse Spark via OpenCode) was used only for language polishing, LaTeX formatting, and consistency checks. All scientific content, experimental design, data collection, analysis and conclusions were performed and verified by the author. No AI-generated data, figures, or references are included. The author takes full responsibility for the content (see `AI_DISCLOSURE.md`).
- *CrossCheck:* We consent to CrossCheck screening. Overlap is expected only with our own arXiv/GitHub preprint.

We suggest reviewers with expertise in calibration-aware compilation/scheduling, quantum-cloud runtime systems, and measurement studies on superconducting devices. We respectfully request that reviewers evaluate the scheduling core (§3–§7) independently of the separable orchestration calculus (Appendix D).

Thank you for considering our measurement study. v8 directly addresses the expected TC concern on single-device generality by extending the inter-day matrix to 4 days/6 pairs and the hourly mechanism to 337 snapshots/71 epochs/3 backends with explicit survival (0% false positives), strengthening the lower-bound claim without new QPU cost.

Sincerely,  
**Y. X. Tan**  
Independent Researcher — yxtan5022@gmail.com  
https://github.com/yxtan5022-maker/unimind-v2 (v8.0-data-release)
