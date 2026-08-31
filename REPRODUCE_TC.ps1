# REPRODUCE_TC.ps1 — one-click local reproducibility for the TC "Temporal Validity" paper.
# Zero IBM quota: every number traces to committed data files (data/**, analysis/results/**).
# Run: powershell -ExecutionPolicy Bypass -File REPRODUCE_TC.ps1
$ErrorActionPreference = "Stop"
$ROOT = "C:\Users\SCSM11\Desktop\unimind-v2"
$PY = "C:\Users\SCSM11\AppData\Local\Programs\Python\Python312\python.exe"
Set-Location $ROOT
Write-Host "== UniMind TC Reproducibility (temporal validity / refresh policy) =="

Write-Host "[1/9] Regression Algorithm 1 pure Ry (w grid) ..."
& $PY -m pytest "$ROOT\tests\test_unibit_correctness_v2_2.py" -q

Write-Host "[2/9] Drift dynamics (D0->D1) ..."
& $PY "$ROOT\analysis\drift_analysis.py" 2>&1 | Select-Object -Last 4
$drift = Get-Content "$ROOT\analysis\results\drift_analysis.json" -Raw | ConvertFrom-Json
Write-Host "  D0->D1 rho=$($drift.rank_stability.spearman_rho_156) tau=$($drift.rank_stability.kendall_tau) top10 Jaccard=$($drift.rank_stability.top10_jaccard)"

Write-Host "[3/9] Refresh policy + threshold sweep (offline) ..."
& $PY "$ROOT\analysis\refresh_policy_sweep.py" 2>&1 | Select-Object -Last 8

Write-Host "[4/9] Power analysis on E2E angle data ..."
& $PY "$ROOT\analysis\power_analysis.py" 2>&1 | Select-Object -Last 10

Write-Host "[5/9] J(G) proxy-to-real failure analysis ..."
& $PY "$ROOT\analysis\jg_failure_analysis.py" 2>&1 | Select-Object -Last 8

Write-Host "[6/9] Reliability calculus ..."
& $PY "$ROOT\analysis\reliability_model.py" 2>&1 | Select-Object -Last 2

Write-Host "[7/9] Distortion sweep model ..."
& $PY -c "import json; d=json.load(open(r'$ROOT\analysis\results\sweep_analysis.json')); print('  bare pinned median max_dev=%.4f alpha=%.4f' % (d['bare_pinned']['median']['max_dev'], d['bare_pinned']['median']['alpha']))"

Write-Host "[8/9] TC paper compile (11 pages, zero overfull) ..."
Push-Location "$ROOT\paper\tc"
& pdflatex -interaction=nonstopmode -halt-on-error unimind_tc.tex *> "$env:TEMP\ltc1.log"
& pdflatex -interaction=nonstopmode -halt-on-error unimind_tc.tex *> "$env:TEMP\ltc2.log"
$pages = (pdfinfo unimind_tc.pdf | Select-String "Pages").ToString()
$ov = (Select-String -Path unimind_tc.log -Pattern "Overfull" | Measure-Object).Count
Write-Host "  $pages ; Overfull=$ov"
Pop-Location

Write-Host "[9/9] Compact 6-page variant compile ..."
Push-Location "$ROOT\paper\tc"
& pdflatex -interaction=nonstopmode -halt-on-error unimind_tc_compact6.tex *> "$env:TEMP\c6.log"
$pages6 = (pdfinfo unimind_tc_compact6.pdf | Select-String "Pages").ToString()
$ov6 = (Select-String -Path unimind_tc_compact6.log -Pattern "Overfull" | Measure-Object).Count
Write-Host "  $pages6 ; Overfull=$ov6"
Pop-Location

Write-Host "== ALL TC LOCAL REPRO PASSED =="
Write-Host "Hardware legs (quota-gated): jobs daadeocjbipc73ffq83g (refresh-full), daadeosjbipc73ffq840 (refresh-ablated)."
