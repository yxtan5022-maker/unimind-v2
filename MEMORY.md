# UniMind v2.0 会话记忆（更新于 2026-08-23 深夜）

## Objective
- v1.7 已提交冻结（`Desktop\论文提交`，勿动）。v2.0 技术评审任务全部完成，全稿已编译。

## Important Details
- 工作区 `C:\Users\SCSM11\Desktop\unimind-v2\`；repo 在 `unimind-dev\`。
- IBM token 已存账户（channel='ibm_quantum_platform'）；后端 ibm_marrakesh；job IDs 记录在 data/qpu_sweep/*.json 元数据。
- **核心结论**：v1.7 硬件失真（0.392）是自由 placement 假象。固定布局后 q98（最优读出 0.44%）bare max_dev 中位 0.028 [0.020–0.029] → 通过 0.05 容差；q37（读出误差 82%）bare 0.213 / twirled 0.144 → 失败；twirling 只对坏比特有益（+33%）。
- 仿射信道 P_obs = b + a·w 全场景 shot-noise 级拟合（q98: 0.004+0.989w；q37: 0.121+0.855w）；评审者的收缩模型 M1 是 b=(1-a)/2 特例，仅在好比特成立，v1.7 冻结数据上 α 跨 0.23–1.31 被拒绝。
- 噪声模型 vs QPU 中位比 1.4×（好比特）——"模型低估硬件"也主要是 placement 问题。
- Ablation：S0→S1 零增益（只贡献 fail-fast 分类）；S1→S2 主力（q=0.5: 58%→92%，q=0.7: 80%→98%）；fallback 窄模板 fr=0.5 仅 +3.1pp，但全覆盖 S3X（9 类意图）达 100%（60/60），fr∈{0.3,0.5} 全吸收。
- Taxonomy：353 注入故障，四类恢复率均匀 82–88%；q=0.5 端到端 91.7% [89.2,93.6]（修正 v1.7 的单种子 94%）。
- Calculus 小节：路径分解恒等式精确成立；朴素独立性预测 ρ_heal=1-(1-q)^4 高估实测（81.5% vs 93.8% @q0.5）→ "相关惩罚"（heal 与 gen 共享同一退化 LLM）。硬件因子与软件层独立，乘法组合仅在有校准检查的固定布局条件下成立。

## Work State
### Completed
- **全量数字验证（2026-08-23）**：论文所有关键数字已对回数据 JSON，逐项通过——QPU sweep（0.028/0.031/0.213/0.144/0.026、affine 拟合 0.989/0.004、0.121+0.855w、1.4×、v17 α 0.23–1.31）、校准快照（q98 0.0044/T1 207/T2 67、q37 82%、设备中位 2.3%，provenance 存 `analysis/results/calib_provenance.json`，与 job 同一时间戳 2026-08-22 22:18:51+08:00）、ablation（58→92、80→98、S3 +0.9/+3.1）、taxonomy（353 故障、四类 CI、91.7 [89.2,93.6]）、calculus 表全部路径数。
- **验证抓到并修复一处错误**：S3X fallback 恢复数实为 **79/79**（fr0.3: 18 + fr0.5: 61），论文误写 60/60 —— 已在 tex 两处和 draft 两处修正并重编译。
- v2.0 全稿组装编译：30 页干净编译，仅剩 v1.7 遗留 2pt overfull。
- 更新点：版本行、摘要（QPU 条款重写 + 新结果句）、贡献列表、5.10–5.13 新小节（sweep/distortion/ablation/taxonomy/calculus）、tab:placement、tab:calculus、Limitations 第1条、T1/T5/T6 威胁段、Phase 1 路线图不变、结论段重写。
- 原 LLM 可靠性小节(94%)保留为 v1.7 单种子协议并加了指向 taxonomy 的衔接句；图注同步。
- 4 张主图（含 S3X 曲线的 fig_ablation）在 paper\figures\，已嵌入 PDF。
- `sections_v2_draft.tex` 与主文件内容一致（S3X 数字已同步）。

### Blocked
- 当前模型不支持图像输入 → PNG 渲染效果需用户人工过目。
- 跨天 drift 验证需另一天执行（明天可用现成命令直接跑）。

## Next Move
1. 用户过目 4 张 PNG 图（paper\figures\*.png）与 30 页 PDF 排版。
2. 明天跑跨天 sweep（命令就绪：python analysis\qpu_sweep.py --cell q98_bare 等）验证 drift，若显著需在文中加注。
3. 可选打磨：把 sections_v2_draft.tex 删除或标注为已并入；arXiv 元数据/zenodo 包如需同步 v2.0 再说。

## Relevant Files
- `unimind-v2\paper\unimind_paper_v2.0.tex` + `.pdf` — v2.0 全稿（30 页）
- `unimind-v2\paper\figures\fig_*.pdf/png` — 4 张主图
- `unimind-v2\analysis\ablation_study.py`（--part quality/stress/stress2）、`make_figures.py`、`test_fallback_v2.py`
- `unimind-v2\analysis\results\*.json` — 所有分析输出
- `unimind-v2\data\qpu_sweep\*.json` — 真机数据（job_id 元数据）
- `unimind-v2\paper\sections_v2_draft.tex` — 草稿（已并入主文件）
