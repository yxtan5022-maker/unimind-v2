# UniMind v2.1 会话记忆（更新于 2026-08-23，RQ1+RQ4 核心完成）

## Objective
- v1.7 冻结于 `Desktop\论文提交`（勿动）；v2.0 冻结为 **tag `v2.0-freeze`**（commit 4f82cd5）。
- 用户指令："启动" RQ1+RQ4 并行、"你直接走就对了"。**两项目前已完成核心交付并提交（commit 99c1120）。**

## Important Details
- **RESEARCH_QUESTIONS.md = v2.1 宪章**（RQ1–RQ5 定义、假设、成功/证伪标准）。
- EXPERIMENTS.md：E-01..E-07 + **A-01/A-02**（分析型登记）。规则：新实验先记 ID 再跑。
- 环境锁 `env\v2.0-environment.txt`；unimind-dev gitlink @6f21bc0。
- **A-01（RQ4，23/23 PASS）**：精确 iid 吸收链模型完全解释 E-03/E-06。ρ_heal 结构公式 g(1−r⁴)/(1−r)；§5.13 "correlation penalty" 解释被证伪——缺口是 **None 中止截断效应**（q=0.5：naive 缺口 12.3pp，结构残差仅 +0.3pp；q=0.7 残差 +4.0pp 在 CI 内）。窄回退涌现覆盖率 c=2/9（no-match 字符串嵌入意图文本，含撇号 → SyntaxError；只有 bell/angle 存活）。干预排序 @q0.5：None 改为只耗槽位 +12.6pp > healer q_h=0.9 (+8.8pp) > 预算翻倍 (+2.1pp)。
- **A-02（RQ1，13/13 PASS）**：collapse ≡ 位置自适应阈值 T_i=τ/g_i；sinc 根 x*=1.3918 ⇒ 尾部 ~56% 位置结构性死区。**三个论文缺陷**：(1) fig:unibit 面板(b) 坐标系编造（s₁₀=−0.0268 在 Eq.(3) 下数学不可能，真实值全非负）；(2) 图注"全零 collapse"错误（真实 s₁=0.7254>τ ⇒ collapse[1]=1），面板(a) w_i 无误；(3) qunibit 多比特 fold 的 X-then-Ry 使 b=1 时 P(1)=1−w_i，与论文声称的纯 Ry 恒等式矛盾（单比特验证实验走无 X 路径故不受影响）。

## Work State
### Completed
- Phase 0 全部 + RQ 宪章 + A-01/A-02 分析与文档：`docs/reliability_model.md`、`docs/unibit_math.md`（各含 v2.1 修正建议清单）、修正图数据 `analysis/results/unibit_fig_data.json`。commit 99c1120。

### Active
- 无进行中任务——等用户决定是否把 A-01/A-02 的修正写入 v2.1 草稿。

### Blocked
- 跨天 drift 验证待明天（E-05 复测）。
- fig:unibit 重绘后的 PDF 效果需用户过目。

## Next Move
1. 用户决策点：(a) 直接开 v2.1 分支落实三项 Unibit 修正 + §5.13 改写（截断效应替代相关性惩罚 + 干预表）；(b) 或继续推进 RQ3/RQ5。
2. 明天：跨天 drift 复测（命令已就绪）。
3. RQ2 下次 QPU session：多比特 sweep ≈24 job（open plan 额度需确认）。

## Relevant Files
- `unimind-v2\RESEARCH_QUESTIONS.md` — RQ 宪章
- `unimind-v2\EXPERIMENTS.md` — 实验登记簿（E-01..E-07, A-01, A-02）
- `unimind-v2\docs\reliability_model.md` / `docs\unibit_math.md` — RQ4/RQ1 交付文档
- `unimind-v2\analysis\reliability_model.py` / `test_unibit_math.py` — 可复现脚本
- `unimind-v2\analysis\results\{reliability_model,unibit_math,unibit_fig_data}.json`
- `unimind-v2\paper\unimind_paper_v2.0.pdf|.tex` — 冻结论文
- `C:\Users\SCSM11\Desktop\论文提交\` — v1.7 冻结目录（只读）

---

# 附录：v2.0 验证记录（保留备查）
- IBM token 已存账户（channel='ibm_quantum_platform'）；后端 ibm_marrakesh；job IDs 记录在 data/qpu_sweep/*.json 元数据。
- **核心结论**：v1.7 硬件失真（0.392）是自由 placement 假象。q98 bare max_dev 中位 0.028 [0.020–0.029] → 通过容差；q37 bare 0.213 / twirled 0.144 → 失败；twirling 只对坏比特有益（+33%）。
- 仿射信道 P_obs = b + a·w 全场景 shot-noise 级拟合；M1 收缩模型是 b=(1-a)/2 特例，仅在好比特成立（v1.7 数据上 α 跨 0.23–1.31 被拒绝）。噪声模型 vs QPU 中位比 1.4×。（A-01 补充：仿射复合封闭性解释了为何两级信道仍仿射。）
- Ablation：S1→S2 主力（+34pp @q0.5）；fallback 窄模板受限，S3X 全覆盖 100%（79/79）。
- Taxonomy：353 故障，四类恢复率均匀 82–88%；q=0.5 端到端 91.7% [89.2,93.6]。
- ~~Calculus：独立性预测高估 ρ_heal → 相关惩罚 −12.2pp~~ **【A-01 已推翻】**：旧计算用朴素基线 1−(1−q)⁴ 忽略 None 中止截断；精确 iid 结构模型残差 ≈0，无需相关性。
- 全量数字对账通过；唯一修正 S3X 60/60→79/79。**【A-02 新增待修】fig:unibit 面板(b) 数据编造 + 图注全零声称错误 + X-then-Ry 语义分歧。**
- 当前模型不支持图像输入 → PNG 渲染需用户人工过目。
- PowerShell 中文路径显示乱码；git commit 用 `-c user.name="Y.X. Tan" -c user.email="yxtan5022@gmail.com"`（repo 未存身份）。
