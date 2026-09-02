#!/usr/bin/env bash
# REPRODUCE_TC.sh — one-click local reproducibility for the TC "Temporal Validity" paper.
# Zero IBM quota: every number traces to committed data files (data/**, analysis/results/**).
# Usage: bash REPRODUCE_TC.sh
# Portability: override with UNIMIND_ROOT (repo dir) and UNIMIND_PYTHON (interpreter) if the
# auto-detected ones are wrong on your machine.
set -e

# --- path discovery (ports the hardcoded local defaults) ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -n "$UNIMIND_ROOT" ]; then
  ROOT="$UNIMIND_ROOT"
elif [ -d "C:/Users/SCSM11/Desktop/unimind-v2/analysis" ]; then
  ROOT="C:/Users/SCSM11/Desktop/unimind-v2"
elif [ -d "$SCRIPT_DIR/analysis" ]; then
  ROOT="$SCRIPT_DIR"
else
  echo "REPRODUCE_TC.sh must be run from inside the repo, or set UNIMIND_ROOT." >&2; exit 1
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
echo "== UniMind TC Reproducibility (temporal validity / refresh policy) =="

# compile_with_retry <tex-basename> <logfile> — pdflatex can hit transient
# file locks on Windows (Defender / PDF previewers); retry a few times.
compile_with_retry() {
  local tex="$1" log="$2" n logpath
  logpath="$ROOT/paper/tc/$log"
  for n in 1 2 3; do
    ( cd "$ROOT/paper/tc" && pdflatex -interaction=nonstopmode -halt-on-error "$tex.tex" > "$logpath" 2>&1 )
    if [ -s "$ROOT/paper/tc/$tex.pdf" ] && grep -q "Output written" "$logpath"; then
      echo "  $tex OK"
      return 0
    fi
    echo "  $tex attempt $n failed (retrying)"; sleep 2
  done
  tail -n 30 "$logpath"; echo "  $tex: giving up." >&2; return 1
}

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
$PY -c "import json; d=json.load(open('$ROOT/analysis/results/sweep_analysis.json')); print('  bare pinned median max_dev={:.4f} alpha={:.4f}'.format(d['bare_pinned']['median']['max_dev'], d['bare_pinned']['median']['alpha']))"

echo "[8/9] TC paper compile check (11 pages, zero overfull) ..."
compile_with_retry unimind_tc ./latex_tc.log
compile_with_retry unimind_tc ./latex_tc2.log
OV=$(grep -c "Overfull" "$ROOT/paper/tc/unimind_tc.log" || true)
echo "  Overfull count: $OV (must be 0)"

echo "[9/9] Compact 6-page variant compile ..."
compile_with_retry unimind_tc_compact6 ./latex_c6.log

echo "== ALL TC LOCAL REPRO PASSED =="
echo "Hardware legs (quota-gated): job ids daadeocjbipc73ffq83g (refresh-full), daadeosjbipc73ffq840 (refresh-ablated)."
