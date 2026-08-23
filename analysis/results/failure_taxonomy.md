# Failure taxonomy -- v1.7 frozen data (mined, not re-run)

## Valid-task outcome paths vs mock quality

| q | n | first_pass | healed | fallback_ok | validation_rejected | failed | success [CI95] |
|---|---|---|---|---|---|---|---|
| 0.5 | 50 | 26 | 21 | 0 | 0 | 3 | 47/50 [0.84,0.98] |
| 0.7 | 50 | 41 | 8 | 0 | 0 | 1 | 49/50 [0.90,1.00] |
| 0.9 | 50 | 50 | 0 | 0 | 0 | 0 | 50/50 [0.93,1.00] |
| 1.0 | 50 | 50 | 0 | 0 | 0 | 0 | 50/50 [0.93,1.00] |

## Injected fault -> recovery

| fault class | n | recovered | rate | CI95 |
|---|---|---|---|---|
| import_violation | 1 | 0 | 0.0% | [0.00,0.79] |
| unspecified_broken_code | 52 | 49 | 94.2% | [0.84,0.98] |

## Cost per outcome path (all qualities pooled)

| path | n | median latency ms | mean LLM calls |
|---|---|---|---|
| first_pass | 167 | 203.575 | 1.192 |
| healed | 29 | 1.804 | 2.448 |
| other_failed | 4 | 1.008 | 2.5 |
