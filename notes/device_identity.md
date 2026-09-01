# UniMind Device Identity Check

_Generated: device_identity.py (script-verified, 2026-09-01)_

## Fleet query result

| Backend | In fleet | Qubits | Operational | n_coupling | coupling (first 5) |
|---|---|---|---|---|---|
| ibm_marrakesh | yes | 156 | True | 352 | [(0, 1), (1, 0), (1, 2), (2, 1), (2, 3)] |
| ibm_fez | yes | 156 | True | 352 | [(0, 1), (1, 0), (1, 2), (2, 1), (2, 3)] |
| ibm_kingston | yes | 156 | True | 352 | [(0, 1), (1, 0), (1, 2), (2, 1), (2, 3)] |

## Conclusions

- **ibm_marrakesh IS still in fleet** (operational: `True`), 156 qubits.
  => D0-D2 closed-loop results remain attributable to ibm_marrakesh; NOT a retired device.
- **ibm_fez**: 156 qubits, 352 edges, operational. 
  Both marrakesh and fez are 156-qubit heavy-hex devices: fez is a SIBLING device, not a successor.
  Continuous telemetry runs on ibm_fez; the telemetry_log.jsonl row timestamps are the source of truth.

### Topology check (heavy-hex 156q?)
- ibm_fez coupling map: 352 edges; sample [(0, 1), (1, 0), (1, 2), (2, 1), (2, 3)]

## Raw fleet dump (all backends, name->qubits)

```json
{
 "ibm_fez": 156,
 "ibm_marrakesh": 156,
 "ibm_kingston": 156
}
```

