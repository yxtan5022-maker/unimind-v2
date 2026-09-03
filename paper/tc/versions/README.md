# UniMind TC paper — milestone versions

Each `vN/` directory is an immutable snapshot of the manuscript at a deliverable milestone.
Files are named `<base>_vN.<ext>` (base = `unimind_tc` extended / `unimind_tc_compact6`).
The current in-progress working copy lives at `paper/tc/unimind_tc.{tex,pdf}` (and `_compact6`).

| version | commit  | pages (ext / compact) | milestone |
|---------|---------|-----------------------|-----------|
| v1      | 9580583 | 11 / 6                | Phase 0 — T_valid rewrite, core-question framing, adaptive refresh policy, power analysis, J(G) proxy-vs-real failure, REPRODUCE_TC |
| v2      | 9e12bf1 | 11 / 6                | Phase 16 — T_valid empirics tied to formal def; refresh-policy + threshold-sweep subsections; reproducibility trace |
| v3      | 4f27571 | 11 / 6                | hyperref bookmark warning fix (texorpdfstring for J(G) section title) |
| v4      | 5d71952 | 12 / 7                | TC Strong P0 — unified Static/Periodic/Adaptive sim, ranking-margin mechanism, J(G) feature ablation, threshold knee |
| v5      | 25951fb | 12 / 7                | TC Strong P1 — workload generalization + connectivity×drift×k |
| v6      | working | 11 / 6                | TC submittable — measurement-study framing, separable App.D, hourly margins, 144-threshold Pareto, Fisher+MDE, ablation+variance, tightened 11p |
| v7      | working | 12 / 6                | TC submit-ready QA — unify 1.94-2.1x across 24-34h D0->D1/D2, fix worst 0.0209/0.0063=3.3x misread, fix margins phrasing, 3 small edits aligned |
| v8      | working | 12 / 6                | TC v8.0-data-release — add D3 (09-01) + D4 (09-02) to 6-pair drift matrix, 337 hourly/71 epochs/3 backends, survival S(t)=1.0 to 15h (0/71), 144-threshold Pareto, submitted 2026-09-03 |

Append a new `vN` on each deliverable milestone; never overwrite an existing one.
