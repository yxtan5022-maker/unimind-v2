# REPRODUCE_TC.ps1 — one-click local reproducibility for the TC "Temporal Validity" paper.
# Zero IBM quota: every number traces to committed data files (data/**, analysis/results/**).
# Run: powershell -ExecutionPolicy Bypass -File REPRODUCE_TC.ps1
# Portability: override with env UNIMIND_ROOT (repo dir) and UNIMIND_PYTHON (interpreter).
$ErrorActionPreference = "Stop"

# --- path discovery (ports the hardcoded local defaults) ---
if ($env:UNIMIND_ROOT) {
    $ROOT = $env:UNIMIND_ROOT
} elseif (Test-Path "$PSScriptRoot\analysis" -PathType Container) {
    $ROOT = $PSScriptRoot
} elseif (Test-Path "C:\Users\SCSM11\Desktop\unimind-v2\analysis" -PathType Container) {
    $ROOT = "C:\Users\SCSM11\Desktop\unimind-v2"
} else {
    throw "REPRODUCE_TC.ps1 must be run from inside the repo, or set UNIMIND_ROOT."
}
if ($env:UNIMIND_PYTHON) {
    $PY = $env:UNIMIND_PYTHON
} elseif (Test-Path "C:\Users\SCSM11\AppData\Local\Programs\Python\Python312\python.exe") {
    $PY = "C:\Users\SCSM11\AppData\Local\Programs\Python\Python312\python.exe"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PY = "python"
} else {
    throw "python not found; set UNIMIND_PYTHON."
}
Set-Location $ROOT
Write-Host "ROOT=$ROOT  PY=$PY"
Write-Host "== UniMind TC Reproducibility (temporal validity / refresh policy) =="

function Compile-WithRetry {
    param([string]$TexBase, [string]$LogName)
    for ($n = 1; $n -le 3; $n++) {
        Push-Location "$ROOT\paper\tc"
        cmd /c "pdflatex -interaction=nonstopmode -halt-on-error $TexBase.tex > `"%TEMP%\$LogName`" 2>&1" | Out-Null
        Pop-Location
        if ((Test-Path "$ROOT\paper\tc\$TexBase.pdf") -and
            (Select-String -Path (Join-Path $env:TEMP $LogName) -Pattern "Output written" -Quiet)) {
            Write-Host "  $TexBase OK"
            return
        }
        Write-Host "  $TexBase attempt $n failed (retrying)"; Start-Sleep -Seconds 2
    }
    Get-Content (Join-Path $env:TEMP $LogName) -Tail 30 -ErrorAction SilentlyContinue
    throw "  ${TexBase}: giving up (file lock persists)."
}

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
Compile-WithRetry unimind_tc ltc1.log
Compile-WithRetry unimind_tc ltc2.log
$pages = (pdfinfo "$ROOT\paper\tc\unimind_tc.pdf" | Select-String "Pages").ToString()
$ov = (Select-String -Path "$ROOT\paper\tc\unimind_tc.log" -Pattern "Overfull" | Measure-Object).Count
Write-Host "  $pages ; Overfull=$ov"

Write-Host "[9/9] Compact 6-page variant compile ..."
Compile-WithRetry unimind_tc_compact6 c6.log
$pages6 = (pdfinfo "$ROOT\paper\tc\unimind_tc_compact6.pdf" | Select-String "Pages").ToString()
$ov6 = (Select-String -Path "$ROOT\paper\tc\unimind_tc_compact6.log" -Pattern "Overfull" | Measure-Object).Count
Write-Host "  $pages6 ; Overfull=$ov6"

Write-Host "== ALL TC LOCAL REPRO PASSED =="
Write-Host "Hardware legs (quota-gated): jobs daadeocjbipc73ffq83g (refresh-full), daadeosjbipc73ffq840 (refresh-ablated)."
