# Telemetry evidence — ibm_fez

These 5 files are **copies** (not moves) of the earliest `ibm_fez` calibration snapshots
pulled by the Task-1 scheduler, chosen because they are the exact snapshots behind
`notes/replication.md`:

| file (this dir) | last_update (capture) | fetched_at | role |
|---|---|---|---|
| `2026-08-31T125233.397116+0000.json` | 2026-08-31 19:56:33+08:00 | 20:52:33 | replication snapshot A (dup 1) |
| `2026-08-31T130404.107337+0000.json` | 2026-08-31 19:56:33+08:00 | 21:04:04 | replication snapshot A (dup 2) |
| `2026-09-01T010557.459596+0000.json` | 2026-09-01 08:24:34+08:00 | 09:05:57 | replication snapshot B (dup 1) |
| `2026-09-01T010647.077209+0000.json` | 2026-09-01 08:24:34+08:00 | 09:06:47 | replication snapshot B (dup 2) |
| `2026-09-01T011054.758563+0000.json` | 2026-09-01 08:24:34+08:00 | 09:10:54 | replication snapshot B (dup 3) |

Schema: `{backend, last_update_date, fetched_at, qubits:[{q,p01,p10,readout_total,T1_us,T2_us,sx_error}]}`.
These sample the same 156-qubit `ibm_fez` sibling used for the drift/telemetry narrative in
Task 3 and the calibration-cadence threat discussion; they postdate the paper's D0–D2 windows.