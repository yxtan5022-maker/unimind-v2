@echo off
REM schedule_tasks.bat -- set up Windows scheduled tasks for fetch_once.py
REM ibm_fez: every 5 minutes; ibm_marrakesh,ibm_kingston: every 15 minutes.
REM Run as Administrator.

set SCRIPT_DIR=%~dp0
set PYTHON=%SCRIPT_DIR%..\env\Scripts\python.exe
set FETCH=%SCRIPT_DIR%fetch_once.py

echo === UniMind telemetry scheduler setup (Windows schtasks) ===

REM Remove old tasks if they exist
schtasks /Delete /TN "UniMind_Fetch_Fez" /F 2>nul
schtasks /Delete /TN "UniMind_Fetch_Others" /F 2>nul

REM ibm_fez every 5 minutes
schtasks /Create /TN "UniMind_Fetch_Fez" ^
  /TR "\"%PYTHON%\" \"%FETCH%\" --backends ibm_fez" ^
  /SC MINUTE /MO 5 /F

REM ibm_marrakesh + ibm_kingston every 15 minutes
schtasks /Create /TN "UniMind_Fetch_Others" ^
  /TR "\"%PYTHON%\" \"%FETCH%\" --backends ibm_marrakesh,ibm_kingston" ^
  /SC MINUTE /MO 15 /F

echo === Tasks created ===
schtasks /Query /TN "UniMind_Fetch_Fez" /V /FO LIST
schtasks /Query /TN "UniMind_Fetch_Others" /V /FO LIST
