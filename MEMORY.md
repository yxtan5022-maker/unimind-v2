# UniMind v2.1 会话记忆（更新于 2026-08-23 深夜，Phase 0 完成）

## Objective
- v1.7 冻结于 `Desktop\论文提交`（勿动）；v2.0 已完成并冻结为 **git tag `v2.0-freeze`**（repo `unimind-v2\.git`，commit 4f82cd5）。
- 新目标（用户定调）：把 UniMind 推进成"有明确研究贡献的系统研究"，按五个 Research Questions 组织全部后续工作。**第一步（已完成）：RQ 正式化。**

## Important Details
- **RESEARCH_QUESTIONS.md = v2.1 宪章**：RQ1 Unibit 数学性质（W1–W5 形式化对象 + H1.1–H1.3，纯数学+仿真）；RQ2 QPU distortion 机理（affine 参数与校准指标的相关性 + held-out 预测；**null 结果预声明可接受**）；RQ3 hardware-aware routing（C(q) 打分、四臂 baseline、开销约束 ms 级）；RQ4 统一可靠性模型（latent-quality 模型解释 -12.2pp 相关惩罚 + 去相关干预实验）；RQ5 E2E 组合验证（NL→…→QPU 全链 ≥30 任务）。依赖顺序：RQ1/RQ4 可立即做（零 QPU 成本），RQ2 下次 QPU session，RQ3 可并行，RQ5 最后。
- EXPERIMENTS.md 已建立：E-01..E-07 全部登记（含 job IDs、种子、参数、数据路径、结论）。规则：新实验先记 ID 再跑。
- 环境锁定 `env\v2.0-environment.txt`（Python 3.12.0 / qiskit 2.5.1 / aer 0.17.2 / runtime 0.49.0 等）。pip freeze 因损坏的 editable 包报错，改用 importlib.metadata 记录关键包。
- unimind-dev 以 gitlink 方式嵌在 v2.0 冻结提交里（其自身 repo 干净 @6f21bc0）。
- v2.0 论文数字已全量对账（见上一节验证），唯一修正：S3X 恢复数 79/79（原误写 60/60）。

## Work State
### Completed
- Phase 0 全部：git init + commit 4f82cd5 + tag v2.0-freeze（含 PDF/tex/数据/图/分析代码/RQ 宪章/实验日志/环境锁）。
- 五个 RQ 正式定义并写入 RESEARCH_QUESTIONS.md（每个含 evidence base、假设、方法、指标、成功/证伪标准、Phase 任务映射）。

### Active
- 无进行中任务——等用户选下一个 RQ 启动。

### Blocked
- 跨天 drift 验证仍待明天（E-05 复测）。

## Next Move
1. **用户决策点：先启动哪个 RQ？** 建议 RQ1+RQ4 并行（纯数学/仿真，无 QPU 成本），下次 QPU session 时同时跑 RQ2 多比特 sweep + 明天的 drift 复测。
2. RQ2 需要的额外 QPU 预算估计：8–10 qubits × 19 weights × bare × 3 jobs ≈ 24 个 job（open plan 当天额度需确认）。
3. 若用户认可 RQ 顺序，从 RQ1 的 docs/unibit_math.md 开始写形式化命题。

## Relevant Files
- `unimind-v2\RESEARCH_QUESTIONS.md` — RQ 宪章（核心）
- `unimind-v2\EXPERIMENTS.md` — 实验登记簿
- `unimind-v2\env\v2.0-environment.txt` — 环境锁
- `unimind-v2\paper\unimind_paper_v2.0.pdf|.tex` — 冻结论文（30 页）
- `unimind-v2\analysis\*`、`data\*`、`analysis\results\*` — 全部代码与数据
- `C:\Users\SCSM11\Desktop\论文提交\` — v1.7 冻结目录（只读）

---

# 附录：v2.0 验证记录（保留备查）
- IBM token 已存账户（channel='ibm_quantum_platform'）；后端 ibm_marrakesh；job IDs 记录在 data/qpu_sweep/*.json 元数据。
- **核心结论**：v1.7 硬件失真（0.392）是自由 placement 假象。q98 bare max_dev 中位 0.028 [0.020–0.029] → 通过容差；q37 bare 0.213 / twirled 0.144 → 失败；twirling 只对坏比特有益（+33%）。
- 仿射信道 P_obs = b + a·w 全场景 shot-noise 级拟合；M1 收缩模型是 b=(1-a)/2 特例，仅在好比特成立（v1.7 数据上 α 跨 0.23–1.31 被拒绝）。噪声模型 vs QPU 中位比 1.4×。
- Ablation：S1→S2 主力（+34pp @q0.5）；fallback 窄模板受限，S3X 全覆盖 100%（79/79）。
- Taxonomy：353 故障，四类恢复率均匀 82–88%；q=0.5 端到端 91.7% [89.2,93.6]。
- Calculus：路径分解精确；独立性预测高估 ρ_heal（81.5% vs 93.8% @q0.5）→ 相关惩罚 −12.2pp。
- 全量数字对账通过（QPU sweep、affine 拟合、校准快照 provenance 同时间戳、ablation、taxonomy、calculus 表）；唯一修正 S3X 60/60→79/79。
- 当前模型不支持图像输入 → PNG 渲染需用户人工过目。
