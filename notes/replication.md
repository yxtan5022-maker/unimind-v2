# Replication check: ibm_fez snapshot pair

Script: `analysis/analyze_replication.py` (all numbers below computed by it)

| item | value |
|---|---|
| snapshot A (last_update) | 2026-08-31 19:56:33+08:00 |
| snapshot B (last_update) | 2026-09-01 08:24:34+08:00 |
| gap (B - A) hours | 12.47 |
| top-1 overlap | 0.000 |
| top-3 overlap | 0.000 |
| top-10 Jaccard | 0.111 |

### Best-qubit (argmin C(q)) drift

| item | A | B | delta |
|---|---|---|---|
| best qubit | 124 | 6 | CHANGED |
| C(best qubit) | 0.00830 | 0.00488 | -0.00342 |
| dC(same qubit 124) (if changed) | - | - | +0.00098 |

### Trigger status

- Jaccard<0.5 firing? **True**  (J10=0.111)
- dC(best)>0.005 firing? **False**  (dC=-0.00342)
- **Trigger FIRING = True**

## Appendix: full top-10 comparison

A top-10: [124, 132, 88, 50, 82, 2, 64, 70, 130, 103]
B top-10: [6, 17, 90, 22, 36, 75, 132, 70, 136, 5]

