@echo off
REM Engine Exporter — Live export runner (BAT wrapper)
REM Calls the PowerShell script.
REM
REM Usage:
REM   scripts\start_live_export.bat status
REM   scripts\start_live_export.bat enable
REM   scripts\start_live_export.bat once
REM   scripts\start_live_export.bat watch

setlocal

set SCRIPT_DIR=%~dp0
set REPO_ROOT=%SCRIPT_DIR%\..

set MODE=%1
if "%MODE%"=="" set MODE=status

if /I "%MODE%"=="status" (
    powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%start_live_export.ps1" -StatusOnly
    goto :end
)
if /I "%MODE%"=="enable" (
    powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%start_live_export.ps1" -Enable
    goto :end
)
if /I "%MODE%"=="once" (
    powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%start_live_export.ps1" -Once
    goto :end
)
if /I "%MODE%"=="watch" (
    powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%start_live_export.ps1" -Watch
    goto :end
)

echo Unknown mode: %MODE%
echo Usage: %~nx0 [status^|enable^|once^|watch]
exit /b 1

:end
exit /b %ERRORLEVEL%
