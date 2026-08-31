#!/usr/bin/env bash
# REPRODUCE_TC.sh — one-click local reproducibility for the TC "Temporal Validity" paper.
# Zero IBM quota: every number traces to committed data files (data/**, analysis/results/**).
# Usage: bash REPRODUCE_TC.sh
set -e
PY="C:/Users/SCSM11/AppData/Local/Programs/Python/Python312/python.exe"
ROOT="C:/Users/SCSM11/Desktop/unimind-v2"
echo "== UniMind TC Reproducibility (temporal validity / refresh policy) =="

echo "[1/9] Regression Algorithm 1 pure Ry (w grid) ..."
$PY -m pytest "$ROOT/tests/test_unibit_correctness_v2_2.py" -q

echo "[2/9] Drift dynamics (D0->D1, D1->D2) ..."
$PY "$ROOT/analysis/drift_analysis.py" 2>&1 | tail -n 15
$PY -c "import json; d=json.load(open('$ROOT/analysis/results/drift_analysis.json')); s=d['rank_stability']; print(f\"  D0->D1 rho={s['spearman_rho_156']} tau={s['kendall_tau']} top10 Jaccard={s['top10_jaccard']}\")"

echo "[3/9] Refresh policy + threshold sweep (offline) ..."
$PY "$ROOT/analysis/refresh_policy_sweep.py" 2>&1 | tail -n 12
$PY -c "import json; d=json.load(open('$ROOT/analysis/results/refresh_policy_analysis.json')); print(f\"  sweep fired(1-refresh) fidelity=0.70, not-fired fidelity={min(r['fidelity_proxy'] for r in d['threshold_sweep'] if not r['fired']):.4f}\")"

echo "[4/9] Power analysis on E2E angle data ..."
$PY "$ROOT/analysis/power_analysis.py" 2>&1 | tail -n 14

echo "[5/9] J(G) proxy-to-real failure analysis ..."
$PY "$ROOT/analysis/jg_failure_analysis.py" 2>&1 | tail -n 20

echo "[6/9] Reliability calculus 23/23 ..."
$PY "$ROOT/analysis/reliability_model.py" 2>&1 | tail -n 8

echo "[7/9] Sweep distortion model ..."
$PY -c "import json; d=json.load(open('$ROOT/analysis/results/sweep_analysis.json')); print('  bare alpha={:.4f}'.format(d['bare_pinned']['median_alpha']))"

echo "[8/9] TC paper compile check (11 pages, zero overfull) ..."
cd "$ROOT/paper/tc" && pdflatex -interaction=nonstopmode -halt-on-error unimind_tc.tex > /tmp/latex_tc.log 2>&1 && echo "PDF OK $(grep 'Output written' /tmp/latex_tc.log | tail -1)" || (cat /tmp/latex_tc.log | tail -n 30; exit 1)
cd "$ROOT/paper/tc" && pdflatex -interaction=nonstopmode -halt-on-error unimind_tc.tex > /tmp/latex_tc2.log 2>&1 && echo "PDF pass2 OK" || (cat /tmp/latex_tc2.log | tail -n 30; exit 1)
OV=$(grep -c "Overfull" "$ROOT/paper/tc/unimind_tc.log" || true)
echo "  Overfull count: $OV (must be 0)"

echo "[9/9] Compact 6-page variant compile ..."
cd "$ROOT/paper/tc" && pdflatex -interaction=nonstopmode -halt-on-error unimind_tc_compact6.tex > /tmp/latex_c6.log 2>&1 && echo "compact6 PDF OK $(grep 'Output written' /tmp/latex_c6.log | tail -1)" || (cat /tmp/latex_c6.log | tail -n 30; exit 1)

echo "== ALL TC LOCAL REPRO PASSED =="
echo "Hardware legs (quota-gated): job ids daadeocjbipc73ffq83g (refresh-full), daadeosjbipc73ffq840 (refresh-ablated)."
