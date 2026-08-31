# Scheduled telemetry pull (invoked by Windows Task Scheduler every 2 h).
# Pulls one snapshot from each of the three 156-qubit backends (0 QPU).
$ErrorActionPreference = "Continue"
$root = "C:\Users\SCSM11\Desktop\unimind-v2"
$log = "$root\data\calib_snapshots\crawler.log"
Set-Location $root
$ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
try {
    & "$root\analysis\telemetry_crawler.py" --once --backends ibm_marrakesh,ibm_kingston,ibm_fez *>> $log
    Add-Content $log "[$ts] OK"
} catch {
    Add-Content $log "[$ts] ERROR $($_.Exception.Message)"
}
