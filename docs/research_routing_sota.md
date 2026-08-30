# Calibration-Aware Routing SOTA (2024-2026) — For UniMind Iterative Optimization

> 生成：2026-08-30 00:20 | 来源：arXiv / IBM / Qiskit | 用途：为 `J(G)=αE_readout+βE_1q+γE_2q+δN_SWAP+λD` 提供可落地加权策略

## 1. Graph Reinforcement Learning for Calibration-Aware Quantum Circuit Routing (arXiv:2606.12816, 2026)

- **来源**: https://arxiv.org/html/2606.12816v2 — same-day IBM Heron r2 calibration data, PPO
- **核心**: 路由开销（SWAP count / depth）小的方案仍可能因穿过校准差的 coupler 而失真。策略将校准感知的图强化学习用于硬件边 SWAP 选择，用当日校准作为状态输入，PPO 训练。
- **公式/策略**: `cost(edge) = -log(1 - p2q_error(edge)) + w_readout·(p01+p10)`, 奖励 = `- (infidelity + λ·depth)`。同日校准预测力最强，跨日泛化下降。
- **映射到 J(G)**: `γ` 应取 `E_2q = Σ -log(1-p2q)` 而非线性 `p2q`，且需同日快照；`U(P)` 的 `λ1·L` 需与 `γ` 联动。UniMind 的 `batch 2026-08-29` 做法（同日 snapshot + `C(q)=p01+p10`）与此一致，但边权重尚未用 `-log` 形式。

## 2. LightSABRE: A Lightweight and Enhanced SABRE Algorithm (arXiv:2409.08368, Zou et al., 2024, IBM)

- **来源**: https://arxiv.org/abs/2409.08368 — IBM 增强版 SABRE
- **核心**: 相对打分（relative scoring）+ 深度/关键路径启发式 + 前瞻窗口。报告在基准上 log-infidelity 降低 12.3%。
- **公式/策略**: `score(SWAP) = decay·H_cost + (1-decay)·lookahead`, `H_cost` 含距离 + 门保真度权重，对关键路径门加权。
- **映射到 J(G)**: `δ·N_SWAP + λ·D` 应拆为 `δ·SWAP + λ_crit·D_crit + λ_avg·D_avg`，关键路径权重 > 平均深度。UniMind 当前仅 `λ·D`，可升级为双深度项。

## 3. Adaptable Weighted Token Swapping for Optimal Multi-Qubit Pathfinding (arXiv:2405.18785v2, Mooney et al.)

- **来源**: https://arxiv.org/html/2405.18785v2
- **核心**: 保真度 =  accumulated SWAP + idling 误差的函数，y 轴为已完成路径的均值。提出自适应加权 token swapping，最优多比特路径搜索。
- **公式/策略**: `Fidelity = Π(1 - p_swap) · Π(1 - p_idle)^{t_idle}`, `cost(token_swap) = w_swap·p_swap + w_idle·p_idle` 自适应于电路 idle 比例。
- **映射到 J(G)**: `E_2q` 需计入 idle 误差（T1/T2 相关），即 `γ·E_2q + γ_idle·E_idle`，其中 `E_idle ∝ depth·(1/T1+1/T2)`。当前 UniMind `E_idle` 未建模。

## 4. Fidelity-Aware Frequency Allocation and Transpilation Co-Design (arXiv:2605.21662, 2025)

- **来源**: https://arxiv.org/html/2605.21662v1 — 提及 LightSABRE 联动
- **核心**: 频率分配与编译协同设计，保真度感知。指出单纯 SWAP 最少 ≠ 保真度最高。
- **映射到 J(G)**: 验证了 `v2` 的 fallback guarantee 合理性：当 calibration 权重与 SWAP 冲突时，应与 Default 取优而非强行覆盖。

## 5. Noise-Adaptive & Error-Aware SWAP (Qiskit NASSC / NAA literature, 2024-2025)

- **来源**: 多篇 NASSC / IEEE QCE 噪声自适应映射（通过 web_search 聚合）
- **核心**: `initial_layout` 噪声自适应（按 readout+1q 排序选连通子图），SWAP 选择时 `cost = error(edge) + decay·distance`。
- **映射到 J(G)**: 正是 UniMind `v2` 的 `w(q)=1/(readout+3·sx)` + `w_e=1/(cz+eps)` 做法，但权重 `3` 为手工，需由 `iterative_optimizer` 搜索最优 `α/β/γ`。

---

### 对 UniMind 的可落地改进（优先级）

1. **P0**: `E_2q` 改 `-log(1-p2q)` 形式，重跑 `utility_model_v2` 的 full-fit，看 `γ` 是否稳定（当前 `γ=0.337`）。
2. **P1**: `J(G)` 拆深度为 `λ_crit·D_crit + λ·D`，或至少在 `iterative_optimizer` 中将 `depth` 替换为 `critical_path_depth`。
3. **P1**: 新增 `E_idle = Σ depth·(1/T1+1/T2)` 项，参数 `γ_idle` 与 `γ` 联合搜索。
4. **P2**: 将 `α/β` 的手工 `3` 系数改为 simplex 采样，由 `iterative_opt_log` 自动收敛（已由 `iterative_optimizer.py` 承接）。

> 以上均零配额本地仿真可验证；同日校准快照要求已由 `daily-drift 21:35` 满足。
