# UniMind Research Questions (v2.1 charter)

Status: DEFINED 2026-08-23, frozen at tag `v2.0-freeze`.
Rule: no new experiment code starts until its RQ hypothesis, metric, and
falsification criterion are recorded here. Results append to EXPERIMENTS.md.

Guiding shift: from "feature-complete middleware" to "system research with
explicit, testable contributions". Each RQ states what v2.0 already
established (evidence base), the precise open question, falsifiable
hypotheses, method, metrics, and success criteria.

---

## RQ1 — What are the mathematical properties of Unibit?

**Question.** Given the pipeline `B -> w_i -> s_i -> theta_i -> P(1)`, what
exactly does each map compute, why is each stage defined as it is, and what
error-propagation guarantees hold end-to-end?

**Evidence base (v2.0).** Ideal-simulator max |Z| deviation 0.0110 over
8192 shots; theta_i = 2 arcsin sqrt(w_i); collapse uses smoothed spectrum
s_i while angles use w_i — the separation is used but never justified.

**Formal objects to deliver (Phase 1, tasks 1.1–1.5).**
- W1: w_i = f(B, window) — normalized bounded functional of binary
  sequence B; state monotonicity and range [0,1].
- W2: s_i = f(B, Delta, phi) via sinc folding — what Delta controls.
- W3: collapse Bhat_i = 1[s_i >= tau] — threshold robustness: collapse
  error exponent vs sinc sidelobe decay in Delta.
- W4: theta_i = 2 arcsin sqrt(w_i) implies P(1) = sin^2(theta_i/2) = w_i
  exactly (noiseless); plus first-order noise propagation under the affine
  channel of RQ2 (sensitivity of E(w) to a_q, b_q).
- W5 (design rationale): a reader-facing argument for why collapse keys on
  s_i while angles key on w_i (Figure-2 separation).

**Hypotheses.**
- H1.1 (identity): on a noiseless backend measured P(1) equals w_i within
  shot noise for all w in {0.05..0.95}. Supported empirically; formalize
  as proposition with proof.
- H1.2 (separation): collapsing on s_i dominates collapsing on raw w_i in
  bit-recovery error rate under single-bit perturbations of B, because
  sinc folding suppresses high-frequency noise.
- H1.3 (angle choice): theta_i = 2 arcsin sqrt(w_i) is the canonical
  single-qubit preparation reproducing P(1)=w_i with no Z-phase dependence;
  argue constructively (minimality, not uniqueness).

**Method.** Pure math + simulator verification only (no QPU cost).

**Success / falsification.**
- Propositions + proofs committed (`docs/unibit_math.md`, then paper Unibit
  section rewritten).
- H1.2 verified if smoothed-collapse error <= raw-collapse error on >=90%
  of the (Delta, tau, flip-rate) grid; falsified if no measurable gain —
  then justify the separation differently or simplify the design.

---

## RQ2 — Why does a real QPU distort the encoding?

**Question.** What physical mechanism generates the affine response
P_obs(1) = b_q + a_q * w observed in E-05, and are (a_q, b_q) predictable
from calibration data alone?

**Evidence base (v2.0).** q98 (readout err 0.44%): P_obs = 0.004 +
0.989*w, RMS 0.0042 < sigma_shot 0.0055; q37 (82%): 0.121 + 0.855*w;
contraction model M1 rejected where asymmetry dominates; noise/QPU ratio
1.4x on good qubits; placement swings max-dev by ~15x.

**Working interpretation (to be tested, not assumed).** For assignment
matrix [[1-e10, e01], [e10, 1-e01]], an ideal P(1)=w maps to
e10 + (1 - e01 - e10)*w: i.e. b_q ~= e10, a_q ~= 1 - e01 - e10.
q98 check: predicts a = 0.9956 vs fitted 0.989 (residual from gate/thermal);
q37 direction matches. Gain loss 1-a_q should further track T1/T2-limited
relaxation during the sequence.

**Hypotheses.**
- H2.1 (offset): fitted b_q correlates with readout asymmetry
  (p(0|1)-p(1|0))/2 or e10 across qubits (Spearman rho > 0.7, p < 0.01).
- H2.2 (gain): a_q <= 1 - e01 - e10 always (composition upper bound), and
  1-a_q increases with idle/gate error budget.
- H2.3 (predictability): regression on calibration features (E_ro, T1, T2,
  sx_err) predicts held-out qubits' tolerance-pass/fail correctly on >=80%
  of held-out set.
- Null outcome explicitly allowed (user directive): if no relationship
  survives, report (a_q,b_q) as free per-qubit parameters and have RQ3
  route purely on measured calibration rather than the affine model.

**Method (Phase 2, tasks 2.2–2.3).** Stratified multi-qubit sweep
(8–10 qubits spanning best-to-worst calibration deciles), 3 jobs/cell,
per-qubit affine fit, correlation analysis + held-out prediction. Reuses
the E-05 harness unchanged (dense grid already done in v2.0).

**Metrics / success.** Per-qubit (a_q,b_q) table; Spearman rho with CIs;
held-out prediction accuracy. Success = H2.1 or H2.3 confirmed; either
outcome (relation found or cleanly nulled) advances the paper.

---

## RQ3 — Can hardware state drive automatic selection of execution resources?

**Question.** Does calibration-aware qubit selection (hardware score
C(q), q* = argmin C(q)) measurably reduce encoding distortion versus
default/free placement, at acceptable routing overhead?

**Evidence base (v2.0).** E-05: max-dev under {free, default-unpinned,
best-calibrated, adversarial} = {0.392, 0.026, 0.028, 0.213}; topology
detection already exists in the codebase but does not influence layout.

**Hypotheses.**
- H3.1 (efficacy): hardware-aware pinning passes the 0.05 tolerance on
  >=90% of randomly drawn target circuits, vs a lower rate for free
  placement, across repeated calibrations.
- H3.2 (score validity): C(q) = alpha*E_ro(q) + beta*(1-a_q proxy) +
  gamma/T1 + delta/T2 — or any monotone variant — ranks qubits such that
  top-1 selection never lands in the failure region characterized in RQ2.
- H3.3 (overhead): transpile-time routing overhead <= O(ms) and is
  negligible vs QPU queue/execution time (report absolute ms).

**Method (Phase 3, tasks 3.1–3.4).** Implement selector over live
backend properties; baseline arms: random / default / best-calibrated /
UniMind-aware; N random layouts x repeat jobs; measure max-dev
distribution, tolerance-pass rate, wall-clock overhead. Depends on RQ2
only for interpretation; can run in parallel.

**Metrics / success.** Tolerance-pass rate per arm with Wilson CIs;
max-dev distributions (min/median/max); routing overhead ms. Success =
H3.1 confirmed AND H3.3 satisfied. This becomes the paper's "solution"
contribution matching the v2.0 "problem" finding.

---

## RQ4 — How should LLM, middleware, and hardware failures be modelled jointly?

**Question.** What is the correct composition rule for end-to-end task
reliability across stages that share components, and how large is the
correlation penalty versus naive independence?

**Evidence base (v2.0).** Exact path decomposition (Eq. composition):
R_end = P(first_pass) + P(enter heal)*rho_heal + P(enter fallback)*rho_fb.
Measured rho_heal 81.5% @q=0.5 vs independence prediction 93.8%:
Delta_corr = -12.2pp (healer shares the degraded LLM). Hardware factor
independent of software path -> multiplicative composition valid only
under pinned calibrated layout.

**Hypotheses.**
- H4.1 (structure): a latent-quality model where generation and healing
  draws are conditionally correlated through shared per-task quality
  (e.g. per-task latent u ~ U(0,1), success iff u < q) reproduces measured
  rho_heal within CI, while the independent model does not.
- H4.2 (quantification): Delta_corr(q) is predictable from (q, f_r,
  retries) analytically under the latent model; verify against new
  simulated configs not used for fitting.
- H4.3 (design implication): decorrelating heal and generate (heterogeneous
  policies in mock) reduces |Delta_corr| by >=50%; test by making healer's
  quality draw partially independent.

**Method (Phase 4, tasks 4.1–4.4).** Formalize R_task and stage events
F_LLM/F_mid/F_quantum; derive joint P(S1 & ... & Sn) under latent-quality
model; extend the E-03/E-04 harness to log per-task draw pairs (already
instrumented); fit + held-out validation; intervention experiment for
H4.3.

**Metrics / success.** Model-vs-empirical rho_heal agreement (CI overlap);
predicted end-to-end R on unseen configs within Wilson CI of measured;
Delta_corr reduction under H4.3 intervention. Success = H4.1+H4.2; this
turns §5.13 into a genuine reliability-model contribution.

---

## RQ5 — Do the composed mechanisms actually improve end-to-end reliability?

**Question.** On the full chain NL -> LLM -> UniMind -> Unibit ->
hardware selection -> QPU -> result, do UniMind's mechanisms (validation,
self-healing, fallback, hardware-aware placement) yield measurable gains
in P_E2E, T_E2E, recovery rate, and quantum fidelity E_Z?

**Evidence base.** All component benchmarks exist separately (E-01..E-07);
no run has ever exercised them together on real hardware.

**Hypotheses.**
- H5.1 (integration): the full chain executes >=30 natural-language task
  specifications end-to-end on ibm_marrakesh without manual intervention.
- H5.2 (gain): P_E2E(full) > P_E2E(with mechanisms ablated), with the
  dominant gain from self-healing + hardware-aware placement (linking
  E-03/E-05 effects into one measurement).
- H5.3 (fidelity): with hardware-aware selection active, reported results
  meet tolerance for >=90% of executed weights (ties to RQ3 outcome).

**Method (Phase 7).** One driver script composing existing modules only
(no new science): 9 intent classes x availability stress x {aware,
default} placement; log every stage transition; report P_E2E, latency
breakdown, recovery counts, E_Z per weight. Mock-vs-real-LLM boundary
documented explicitly.

**Metrics / success.** P_E2E with CI; T_E2E median [P10,P90]; per-stage
recovery matrix; E_Z vs tolerance. Success = H5.1 executed AND H5.2 gain
outside CI overlap. This is the paper's closing evidence.

---

## Dependency order and parallelism

    RQ1 (math only)          -- independent, start anytime
    RQ2 (multi-qubit sweep)  -- next QPU session
    RQ3 (routing)            -- after or parallel to RQ2 (needs no affine model)
    RQ4 (reliability model)  -- independent of QPU; sim-only
    RQ5 (E2E)                -- last; composes RQ2/RQ3/RQ4 outcomes

Minimum publishable increment: RQ1 + RQ2 + RQ4 (one QPU session + math +
sim work). RQ3 adds the solution story; RQ5 closes the loop.

## Global protocols (apply to every experiment)

- Statistics (Phase 6): n, mean, SD, Wilson/Jeffreys CI, seeds, repeats,
  environment lockfile, raw data committed before analysis claims.
- Every QPU job stores job_id + calibration snapshot inside its JSON.
- Negative results are recorded as outcomes, not failures (RQ2 null branch
  is pre-declared).

