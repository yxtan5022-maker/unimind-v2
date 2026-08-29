#!/usr/bin/env bash
# RUN_HARDWARE_BATCH.sh — one-shot quota batch (8 jobs total)
# Prereq: all local repro passed (bash REPRODUCE_v2.2.sh)
# Consumes: 6× E-08 stratified sweeps + 2× E-09 E2E batched PUB jobs
# Safe to re-run: existing router_sweep_q*.json / e2e_*_pending.json are skipped
set -e
PY="C:/Users/SCSM11/AppData/Local/Programs/Python/Python312/python.exe"
ROOT="C:/Users/SCSM11/Desktop/unimind-v2"
echo "== HARDWARE BATCH START $(date -u) =="
echo "Instance: unimind 3.0 / open  Backend: ibm_marrakesh"
echo "Snapshot: $(cat $ROOT/analysis/results/calib_full_e08.json | grep last_update_date | head -1)"

echo "[1/3] E-08 stratified 6-qubit bare sweeps (6 jobs, 19*8192 shots each) ..."
$PY "$ROOT/analysis/hw_router.py" --part qpu 2>&1 | tee "$ROOT/data/qpu_sweep/hw_batch_qpu.log"

echo "[2/3] E-09 E2E submit (2 batched PUB jobs) ..."
$PY "$ROOT/analysis/e2e_chain.py" --stage submit 2>&1 | tee "$ROOT/data/e2e/e2e_batch_submit.log"

echo "[3/3] Collect (if jobs already finished) ..."
$PY "$ROOT/analysis/e2e_chain.py" --stage collect 2>&1 | tee "$ROOT/data/e2e/e2e_batch_collect.log" || echo "collect pending — jobs still queued, re-run this stage later"
$PY "$ROOT/analysis/hw_router.py" --part analyze 2>&1 | tee "$ROOT/analysis/results/hw_batch_analyze.log" || echo "analyze pending — waiting for qpu sweeps"

echo "== BATCH DONE $(date -u) =="
echo "Next: fill paper §5.14 + Table 3 with job_ids from data/qpu_sweep/router_sweep_q*.json and data/e2e/*.json"
