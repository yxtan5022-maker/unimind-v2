#!/usr/bin/env bash
# REPRODUCE v2.2 — one-click local reproducibility (no IBM quota)
# Usage: bash REPRODUCE_v2.2.sh
set -e
PY="C:/Users/SCSM11/AppData/Local/Programs/Python/Python312/python.exe"
ROOT="C:/Users/SCSM11/Desktop/unimind-v2"
echo "== UniMind v2.2 Reproducibility =="
echo "[1/5] Regression Algorithm 1 (w grid) ..."
$PY "$ROOT/tests/test_unibit_correctness_v2_2.py"
echo "[2/5] Cross-framework baseline (Qiskit/PennyLane/UniMind) ..."
$PY "$ROOT/analysis/cross_framework_real.py" | tail -n 20
echo "[3/5] Unibit math audit ..."
$PY "$ROOT/analysis/test_unibit_math.py" 2>&1 | tail -n 20
echo "[4/5] Reliability calculus ..."
$PY "$ROOT/analysis/reliability_model.py" 2>&1 | tail -n 20
echo "[5/5] Paper compile check ..."
cd "$ROOT/paper" && latexmk -pdf -interaction=nonstopmode -halt-on-error unimind_paper_v2.2.tex > /tmp/latex.log 2>&1 && echo "PDF OK" || (cat /tmp/latex.log | tail -n 30; exit 1)
echo "== ALL LOCAL REPRO PASSED =="
echo "Hardware legs (quota): bash RUN_HARDWARE_BATCH.sh"
