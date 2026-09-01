# Scheduled telemetry pull (invoked by Windows Task Scheduler hourly).
# Pulls one snapshot from each of the three 156-qubit backends (0 QPU).
# Rewritten for robustness: uses the explicit python.exe path (no .py file
# association dependency), captures stdout+stderr into variables (no fragile
# native `*>>` redirection), and truthfully reports success ONLY when snapshot
# files were actually written (verifies the on-disk count), so a silent python
# failure can never be logged as "OK".
$ErrorActionPreference = "Continue"
$root    = "C:\Users\SCSM11\Desktop\unimind-v2"
$log     = "$root\data\calib_snapshots\crawler.log"
$python  = "C:\Users\SCSM11\AppData\Local\Programs\Python\Python312\python.exe"
$script  = "$root\analysis\telemetry_crawler.py"
$backends = "ibm_marrakesh,ibm_kingston,ibm_fez"
$ts   = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

# --- count current telemetry rows before we start ---
$before = 0
if (Test-Path "$root\data\calib_snapshots\telemetry_log.jsonl") {
    $before = (Get-Content "$root\data\calib_snapshots\telemetry_log.jsonl").Count
}

try {
    Set-Location $root
    $out = & $python $script --once --backends $backends 2>&1
    $text = ($out | Out-String)

    # --- verify data actually landed (a new telemetry row exists) ---
    $after = (Get-Content "$root\data\calib_snapshots\telemetry_log.jsonl").Count
    if ($after -gt $before) {
        Add-Content $log "[$ts] OK  rows $before -> $after"
        ($text -split "`n" | Select-Object -Last 3) | ForEach-Object {
            if ($_) { Add-Content $log "      $_" }
        }
    } else {
        Add-Content $log "[$ts] ERROR: no new telemetry row written ($before -> $after)"
        Add-Content $log "      $text"
    }
} catch {
    Add-Content $log "[$ts] ERROR $($_.Exception.Message)"
    if ($_.Exception.InnerException) {
        Add-Content $log "      inner: $($_.Exception.InnerException.Message)"
    }
}
