# UniMind Ultimate Roadmap — v2.1 → 极限版 Master Plan
> 收拢自 2026-08-29 讨论，区分 A/B/C/D，可直接作为后续所有工作的 single source of truth。
> 起点: `paper/unimind_paper_v2.1.tex` (36页，已含 LLM orchestration / 三阶段校验 / Unibit / multi-backend / C++/Rust/Python / baseline / fault/noise/sandbox / QPU / calibration-routing / ablation / reliability calculus / E2E composition)

---

## P0 — 不完成不要投 (封死漏洞 + 补齐证据)

### 01 Algorithm 1 正确性
- **问题**: X/Ry 顺序致 `b_i=1` 时 `P(1)=1-w` 而非 `w`，论文已 self-disclose
- **动作**: 修正算法伪代码 + 代码实现统一，`w∈{0,0.05,...,1}` 回归测试，`|P_emp(1)-w|<ε`，入 CI
- **交付**: `sections/method.tex` Algorithm 1 更新 + `tests/test_unibit_correctness.py` + CI log

### 02 Physical E2E 闭环
- 现状: 软件 54/54=100%, ablated 47/54=87%, physical fidelity leg 在 queue
- **必须补**: `Intent→LLM→Validation→Healing→Routing→QPU→Measurement` 真机端到端数据，至少 1 完整 run + 表格

### 03 Cross-framework 竞争基线
- 对比: Qiskit-native / PennyLane / (可选)CUDA-Q vs UniMind
- **维度**: hardware discovery / backend selection / calibration-aware routing / failure recovery / fallback / intent orchestration / safety validation / human intervention — 不是只比 circuit time
- **意义**: 回应 v2.1 Limitation，否则 reviewer 一句 "why not just use Qiskit?" 即死

### 04 Reproducibility Pipeline
- 一键复现: calibration snapshot / seed / table3 0.0110 偏差 / Rust 2.4-4.5× / NumPy 7.5-10.9×

---

## P1 — 从"不错"推到"强" (7个 RQ 驱动)

对应最终实验矩阵 7 RQ，所有 Fig/Table 必须回答某 RQ:

| RQ | 问题 | 关键实验 |
|---|---|---|
| RQ1 | Hardware awareness 有用吗 | placement vs random/default |
| RQ2 | Reliability-aware routing 有用吗 | 5策略对比 SWAP/depth/fidelity |
| RQ3 | LLM 有价值吗 | LLM vs rule-based dispatcher |
| RQ4 | Generalize 吗 | 7类 workload (classical/GPU/quantum/comm/sync/fault/calibration-sensitive) |
| RQ5 | 应对 drift 吗 | multi-day D1-D5 + stale calibration (昨天数据今天跑) |
| RQ6 | 扩展到 multi-qubit 吗 | 2/4/6/8/10/16 qubits routing |
| RQ7 | 失败后能恢复吗 | fault→diagnosis→recovery→replan 测 latency/accuracy/success |

**P1 任务拆解**:
- **06 Multi-day validation**: D1-D5 每天取 calibration 算 C(q) 排名，跑同 workload 测 distortion，算 ρ(C(q),E(q))，证 ρ≈1 非单日偶然
- **07 Real LLM**: 2-3 真模型 ×100-300 tasks，测 P(valid)/P(heal)/P(fallback)/P(failure)/latency，验 R_predicted vs R_observed
- **08 Multi-qubit routing**: q*→G* 升级，G*=argmax R_circuit(G)，测 SWAP/depth/2q error/latency/fidelity
- **09 Reliability-aware**: J(G)=αE_readout+βE_1q+γE_2q+δN_SWAP+λD，argmax R_task(G)
- **10 Unified Utility**: U(P)=P_success -λ1L -λ2C -λ3E，带约束 R≥Rmin,L≤Lmax,C≤Cmax，统一 routing/reliability/latency/fallback
- **11 Workload generalization**: 7类 workload 证非 Unibit 特化
- **12 Self-healing closed loop**: s_t=(T,H_t,R_t), a_t=π(s_t), s_{t+1}=f(s_t,a_t,o_t)，实现 Observe→Update→Replan
- **13 Stale calibration**: ΔC>C_threshold 触发 refresh→rerank→reroute，证 adaptive 非静态表

---

## P2 — 冲极限 (有余力再做)

14 Adaptive replanning (online 策略切换)
15 Counterfactual: calibration(LLM/hardware) normal→noisy→stale→adversarial 压力测试
16 Correlated failure: 测 P(F_t|F_{t-1}) 替代 i.i.d. 假设
17 Formal bounds: R_lower ≤ R_obs ≤ R_upper
18 Online calibration update
19 Second physical device
20 Larger-scale circuits

---

## 架构收束 (Ultimate)

```
USER Intent → [LLM Untrusted Planner] → [Deterministic Validation/Sandbox] → [Reliability Estimator] → [Adaptive Scheduler maximize U(P)] → CPU/GPU/QPU → Physical Feedback → State Update → Re-plan
```
**核心原则**: `LLM failure ⇏ system failure` / `Probabilistic intelligence must be enclosed by deterministic guarantees` / 维护 Confidence (plan/hardware/fidelity/overall risk)，R<Rmin 则不盲执行

## 论文新结构 (12章)

1 Introduction  2 Motivation & Design Principles  3 Execution Model (task/hardware/reliability/objective)  4 System Design (LLM/validation/estimator/scheduler/routing/self-healing)  5 Implementation  6 Analytical Model (reliability/utility/bounds)  7 Methodology  8 Evaluation (RQ1-7)  9 Ablation  10 Limitations  11 Related Work  12 Conclusion

## D — 明确砍掉/降权

- ❌ 再加 backend 数量 (已有4个够，贡献是 One abstraction→Many envs)
- ❌ Unibit 做中心 (降为 representative workload transformation)
- ❌ Security 抢主线 (保留 20/21 blocked 证明 constrained generation 即可)
- ❌ 新 AI agent / 十几个 skill / 炫酷 UI / 复杂量子算法
- ✅ 要: 把已有东西用 U(P) + reliability calculus + closed-loop 统一起来

---

## 一句话检验

> UniMind 能否在 不确定LLM + 动态calibration + noisy QPU + 异构硬件 环境中，持续选择可靠执行计划，并在失败/环境变化后自行调整？

若证 `Plan+Validate+Estimate+Optimize+Execute+Observe+Adapt` 有 formal model + prototype + real LLM + real QPU + multi-day + multi-qubit + competing baseline + ablation + reproducible，则不再是 "quantum middleware"，而是 "面向不确定异构量子-经典环境的可靠自适应执行机制"。

---
*Source: 2026-08-29 路线图整理，优先级 P0(01-05) → P1(06-13) → P2(14-20)*
