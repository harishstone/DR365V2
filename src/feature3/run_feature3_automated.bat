@echo off
REM Automated Feature 3 Execution
REM Step 1: Run PowerShell to collect data
REM Step 2: Run Python to analyze and write to database

cd /d "C:\DR365\DR365V2\src\feature3"

echo ========================================
echo Feature 3: Automated Execution
echo ========================================
echo.

REM Run PowerShell script
echo Step 1: Collecting efficiency data via PowerShell...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Add-PSSnapin VeeamPSSnapin; Set-Location 'C:\DR365\DR365V2\src\feature3'; .\get_efficiency_data.ps1 -DaysBack 30"

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: PowerShell script failed
    exit /b 1
)

echo.
echo Step 2: Analyzing data with Python...
python "C:\DR365\DR365V2\src\feature3\feature3_from_json.py"

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python script failed
    exit /b 1
)

echo.
echo ========================================
echo Feature 3: Completed Successfully
echo ========================================
exit /b 0
