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
| v5      | 25951fb | 12 / 7                | TC Strong P1 — workload generalization + connectivity×drift×k (current) |
| v6      |         | 12 / 7                | TC Strong P2 — honesty pass: device-identity footnote (b), calibration-cadence threat (a), Huo & Wei related work + bibitem (c), pinned-vs-free indistinguishability wording (d) |

Append a new `vN` on each deliverable milestone; never overwrite an existing one.
