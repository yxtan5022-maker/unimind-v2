# Gates: UniMind v2 — 全量收束 (容许失败的科学)

OWNS: analysis/**, data/**, docs/**, paper/**, tests/**, results/**, GATES.md

Scope: 接管后把 v2.3已提交 + v2.4未提交 全部收敛为可复现、可诚实报告失败的版本；不删失败，只记录失败。

> 用户指令: "这些东西都要，这并不是一道选择题，除了c吧" + "科学好像是一定成功的，不能容许失败的" —— 反驳该观念：所有门槛必须同时报告成功与失败，失败本身是证据。

- [ ] G1: Git 脏区清理与基线可复现
  CHECK: bash -c "cd C:/Users/SCSM11/Desktop/unimind-v2 && git status --porcelain | cat; python tests/test_unibit_correctness_v2_2.py 2>&1 | tail -5"
  EXPECT: PASS
  EVIDENCE: 2026-08-30 git status --porcelain 63 lines (5 staged: EXPERIMENTS.md, utility_model_v4.json, fig_router.pdf, v2.4.tex, v2.5.tex; 8 modified-not-staged; 55 untracked incl. GATES.md/tests/results); staged diff --stat 5 files +5020 ins; branch master

- [ ] G2: 本地全量 REPRODUCE_v2.2 通过 (5/5) 且论文可编译
  CHECK: bash -c "cd C:/Users/SCSM11/Desktop/unimind-v2 && python analysis/test_unibit_math.py 2>&1 | tail -3; python analysis/reliability_model.py 2>&1 | tail -3"
  EXPECT: 23/23
  EVIDENCE: 2026-08-30 test_unibit_math.py 13/13 passed (P1a-e,P2a-e,P3a-c,P4,P5) -> analysis/results/unibit_math.json; reliability_model.py 23/23 passed (E03 15/15 Wilson CI + E06 8/8 incl. narrow-fallback) -> analysis/results/reliability_model.json

- [ ] G3: J(G) 7维模型诚实化 — 报告过拟合与截断失败
  CHECK: bash -c "cd C:/Users/SCSM11/Desktop/unimind-v2 && python -c \"import json; d=json.load(open('analysis/results/j_holdout.json')); print('holdout_rho', d['test']['rho']); print('oob_clipped', d['test']['oob_clipped']); print('n_train', d['train']['n'])\""
  EXPECT: holdout_rho
  EVIDENCE: 2026-08-30 utility_model_v4.json n=23 (6 single +17 multi) 7-dim J(G)=alpha*E_readout+beta*E_1q+gamma*E_2q+gamma_log*E_2q_log+eta_idle*E_idle+delta*N_SWAP+lambda_*D; full rho=0.9674 p=0.0; LOO rho=0.9526 p=0.0 mean_train_rho=0.9694 std=0.0063; params beta=0.3345 gamma=0.3708 dominant

- [ ] G4: 硬件数据诚实化 — E2E 74.1% vs 66.7% CI重叠、H3.1 fail、q109/q53 等反常
  CHECK: bash -c "cd C:/Users/SCSM11/Desktop/unimind-v2 && cat data/e2e/e2e_summary.json; echo '---'; cat analysis/results/router_analysis.json | python -c \"import json,sys; d=json.load(sys.stdin); print([c for c in d['cells']]); print(d['verdicts'])\""
  EXPECT: E2E CI overlap documented as fail, H3.1 fail documented
  EVIDENCE: 2026-08-30 e2e_summary.json P_E2E_full 74.1%[61.1,83.9] vs ablated 66.7%[53.4,77.8] CI overlap not significant (honest fail); H3.1 q109 73.7%<90% fail, q53 100% pass; router_analysis.json Spearman rho0.771 p0.103 not significant (n=6); verdicts H3.2 pass, H3.1 fail, overhead selector 0.0246ms pinned 1.9ms

- [ ] G5: Multi-qubit routing v2/v3 可复现 (k=2..16, 5策略, 不劣于Default)
  CHECK: bash -c "cd C:/Users/SCSM11/Desktop/unimind-v2 && cat analysis/results/multi_qubit_routing_v2.md | head -80"
  EXPECT: UniMind ties Default for k>=8, beats Random 76-100%
  EVIDENCE: 2026-08-30 multi_qubit_routing_v2.json k={2,4,6,8,10,16} swap_vs_default +0 for all k>=4 (fallback guarantee), swap_reduction_vs_random 0.76-1.0, k16 0.758; meta snapshot 2026-08-29 21:26:27 156q 176edges FakeMarrakesh

- [ ] G6: 失败即证据 — 论文 Limitations/Threats 显式写入所有阴性结果
  CHECK: bash -c "cd C:/Users/SCSM11/Desktop/unimind-v2 && grep -n 'fail\|limit\|threat\|overlap\|clipped\|oob\|H3.1' paper/unimind_paper_v2.4.tex | head -20"
  EXPECT: all fails written into paper Limitations
  EVIDENCE: 2026-08-30 paper v2.5 Stage2 Limitations H3.1 fail q109 73.7% + rho0.771 not significant; Stage3 v3 n=9 overfit LOO 0.667 fragile oob_clipped true now resolved to v4 n23 LOO0.953; E2E CI overlap documented

- [ ] G7: Paper v2.4 编译通过且无引用断裂
  CHECK: bash -c "cd C:/Users/SCSM11/Desktop/unimind-v2/paper && pdflatex -interaction=nonstopmode -halt-on-error unimind_paper_v2.5.tex 2>&1 | grep Output; pdflatex -interaction=nonstopmode unimind_paper_v2.5.tex 2>&1 | grep -E "undefined|Error" | head -5"
  EXPECT: Output written on unimind_paper_v2.5.pdf (38 pages, 818241 bytes) 0 undefined refs
  EVIDENCE: 2026-08-30 pdflatex x2 pass2 0 undefined, fig_router.pdf/png co-generated 0.27s delta

- [ ] G8: 交付物归档 — 无散落根目录、3件套逻辑就绪(华文/英文/短视频版预留)
  CHECK: bash -c "ls -R C:/Users/SCSM11/Desktop/unimind-v2 2>&1 | head -40"
  EXPECT: no stray root files, figures fresh 11:03
  EVIDENCE: 2026-08-30 git ls-files --others shows 47 untracked (synthetic intermediates documented), paper/figures 5 pdf fresh 11:03, staged 6 files (+fig_router.png), REPRODUCE_v2.5.sh 6/6 ALL PASSED
