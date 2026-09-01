# Nightly survival-analysis checkpoint.
# Runs survival_analysis.py over the accumulated telemetry snapshots, generates
# the KM-curve figure (via plot_survival.py), and copies the JSON result to the
# desktop mirror so the user can review progress without diving into the repo.
$ErrorActionPreference = "Continue"
$root    = "C:\Users\SCSM11\Desktop\unimind-v2"
$python  = "C:\Users\SCSM11\AppData\Local\Programs\Python\Python312\python.exe"
$dest    = "C:\Users\SCSM11\Desktop\unimind-telemetry-data_2026-09-01"
$ts      = Get-Date -Format "yyyy-MM-dd HH:mm"

# make sure we have the latest data (crawler + desktop mirror) before analyzing
& "$root\analysis\telemetry_scheduled.ps1"

$out = & $python "$root\analysis\survival_analysis.py" --json 2>&1
$out | ForEach-Object { $_ }
Add-Content "$root\data\calib_snapshots\crawler.log" "[$ts] SURVIVAL-CHECKPOINT"

# regenerate KM figure so the latest survival curve is rendered
& $python "$root\analysis\plot_survival.py" 2>&1 | ForEach-Object { $_ }

# copy result + figure to desktop mirror
New-Item -ItemType Directory -Path "$dest\figures" -Force | Out-Null
if (Test-Path "$root\analysis\results\survival_analysis.json") {
    Copy-Item "$root\analysis\results\survival_analysis.json" "$dest" -Force
}
Get-ChildItem "$root\analysis\figures\*.pdf" -ErrorAction SilentlyContinue |
    ForEach-Object { Copy-Item $_.FullName "$dest\figures" -Force }
Write-Output "[done] survival checkpoint -> $dest"
