@echo off
REM Wrapper to call PowerShell script from Python

cd /d "%~dp0"

REM Use PowerShell 7 (pwsh.exe) which can load Veeam modules
pwsh.exe -NoProfile -ExecutionPolicy Bypass -File "get_efficiency_data.ps1" -DaysBack %1 -OutputPath %2

exit /b %ERRORLEVEL%
