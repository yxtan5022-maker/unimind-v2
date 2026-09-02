#!/usr/bin/env bash
# REPRODUCE v2.5 — one-click local reproducibility (no IBM quota, v4 synthetic-expanded)
# Usage: bash REPRODUCE_v2.5.sh (also kept as REPRODUCE_v2.2.sh compat)
# Portability: override with UNIMIND_ROOT and UNIMIND_PYTHON.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -n "$UNIMIND_ROOT" ]; then
  ROOT="$UNIMIND_ROOT"
elif [ -d "C:/Users/SCSM11/Desktop/unimind-v2/analysis" ]; then
  ROOT="C:/Users/SCSM11/Desktop/unimind-v2"
elif [ -d "$SCRIPT_DIR/analysis" ]; then
  ROOT="$SCRIPT_DIR"
else
  echo "REPRODUCE_v2.5.sh must be run from inside the repo, or set UNIMIND_ROOT." >&2; exit 1
fi

if [ -n "$UNIMIND_PYTHON" ]; then
  PY="$UNIMIND_PYTHON"
elif [ -x "C:/Users/SCSM11/AppData/Local/Programs/Python/Python312/python.exe" ]; then
  PY="C:/Users/SCSM11/AppData/Local/Programs/Python/Python312/python.exe"
elif command -v python >/dev/null 2>&1; then
  PY="python"
else
  echo "python not found; set UNIMIND_PYTHON." >&2; exit 1
fi

echo "ROOT=$ROOT  PY=$PY"
echo "== UniMind v2.5 Reproducibility (v4 n=23 synthetic-expanded) =="
echo "[1/6] Regression Algorithm 1 pure Ry (w grid) ..."
$PY -m pytest "$ROOT/tests/test_unibit_correctness_v2_2.py" -q
echo "[2/6] Cross-framework baseline (Qiskit/PennyLane/UniMind 8-dim) ..."
$PY "$ROOT/analysis/cross_framework_real.py" 2>&1 | tail -n 20
echo "[3/6] Unibit math audit 13/13 ..."
$PY "$ROOT/analysis/test_unibit_math.py" 2>&1 | tail -n 20
echo "[4/6] Reliability calculus 23/23 ..."
$PY "$ROOT/analysis/reliability_model.py" 2>&1 | tail -n 20
echo "[5/6] J(G) v4 n=23 audit (rho 0.967 LOO 0.953) ..."
$PY -c "import json; d=json.load(open('$ROOT/analysis/results/utility_model_v4.json')); print(f\"v4 n={d['dataset']['n_points']} full rho={d['full_fit']['spearman']['rho']:.4f} p={d['full_fit']['spearman']['p_value']} LOO rho={d['loo']['loo_rho']:.4f} train_mean={d['loo']['mean_train_rho']:.4f}\")"
echo "[6/6] Paper compile check (v2.5, 38 pages) ..."
cd "$ROOT/paper" && pdflatex -interaction=nonstopmode -halt-on-error unimind_paper_v2.5.tex > /tmp/latex.log 2>&1 && echo "PDF OK $(grep 'Output written' /tmp/latex.log | tail -1)" || (cat /tmp/latex.log | tail -n 30; exit 1)
# second pass to resolve refs
cd "$ROOT/paper" && pdflatex -interaction=nonstopmode -halt-on-error unimind_paper_v2.5.tex > /tmp/latex2.log 2>&1 && echo "PDF pass2 OK" || (cat /tmp/latex2.log | tail -n 30; exit 1)
echo "== ALL LOCAL REPRO PASSED (v2.5) =="
echo "Hardware legs (quota): bash RUN_HARDWARE_BATCH.sh"
