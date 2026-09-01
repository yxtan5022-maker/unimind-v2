#!/usr/bin/env bash
# schedule_tasks_cron.sh -- set up cron jobs for fetch_once.py
# ibm_fez: every 5 minutes; ibm_marrakesh,ibm_kingston: every 15 minutes.
# Linux/Mac only.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${SCRIPT_DIR}/../env/bin/python3"
FETCH="${SCRIPT_DIR}/fetch_once.py"

echo "=== UniMind telemetry scheduler setup (cron) ==="

# Remove old entries
crontab -l 2>/dev/null | grep -v "UniMind_Fetch" | crontab - 2>/dev/null || true

# ibm_fez every 5 minutes
(crontab -l 2>/dev/null; echo "*/5 * * * * ${PYTHON} ${FETCH} --backends ibm_fez # UniMind_Fetch_Fez") | crontab -

# ibm_marrakesh + ibm_kingston every 15 minutes
(crontab -l 2>/dev/null; echo "*/15 * * * * ${PYTHON} ${FETCH} --backends ibm_marrakesh,ibm_kingston # UniMind_Fetch_Others") | crontab -

echo "=== Cron entries installed ==="
crontab -l | grep UniMind
