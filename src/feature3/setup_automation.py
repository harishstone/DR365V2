# Feature 3 Automation Setup Script
# This creates a Windows Scheduled Task to run Feature 3 automatically

import subprocess
import os
import sys

def create_scheduled_task():
    """Create Windows Scheduled Task for Feature 3"""
    
    # Paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ps_script = os.path.join(script_dir, "get_efficiency_data.ps1")
    python_script = os.path.join(script_dir, "feature3_from_json.py")
    
    # Task name
    task_name = "DR365_Feature3_Daily"
    
    # PowerShell command that will run in VBR context
    # This uses the VBR PowerShell module directly
    ps_command = f'''
    Add-PSSnapin VeeamPSSnapin -ErrorAction SilentlyContinue
    Set-Location "{script_dir}"
    .\\get_efficiency_data.ps1 -DaysBack 30
    '''
    
    # Create batch file that runs PowerShell then Python
    batch_file = os.path.join(script_dir, "run_feature3_automated.bat")
    
    with open(batch_file, 'w') as f:
        f.write(f'''@echo off
REM Automated Feature 3 Execution
REM Step 1: Run PowerShell to collect data
REM Step 2: Run Python to analyze and write to database

cd /d "{script_dir}"

echo ========================================
echo Feature 3: Automated Execution
echo ========================================
echo.

REM Run PowerShell script
echo Step 1: Collecting efficiency data via PowerShell...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Add-PSSnapin VeeamPSSnapin; Set-Location '{script_dir}'; .\\get_efficiency_data.ps1 -DaysBack 30"

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: PowerShell script failed
    exit /b 1
)

echo.
echo Step 2: Analyzing data with Python...
python "{python_script}"

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python script failed
    exit /b 1
)

echo.
echo ========================================
echo Feature 3: Completed Successfully
echo ========================================
exit /b 0
''')
    
    print(f"[OK] Created batch file: {batch_file}")
    
    # Create the scheduled task using schtasks
    # Run daily at 1:00 AM
    schtasks_command = [
        'schtasks',
        '/Create',
        '/TN', task_name,
        '/TR', f'"{batch_file}"',
        '/SC', 'DAILY',
        '/ST', '01:00',
        '/RU', 'SYSTEM',
        '/RL', 'HIGHEST',
        '/F'  # Force create (overwrite if exists)
    ]
    
    print(f"\n[*] Creating scheduled task: {task_name}")
    print(f"   Schedule: Daily at 1:00 AM")
    print(f"   Command: {batch_file}")
    
    try:
        result = subprocess.run(schtasks_command, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"\n[OK] Scheduled task created successfully!")
            print(f"\nTo view the task:")
            print(f"   schtasks /Query /TN {task_name} /V /FO LIST")
            print(f"\nTo run it manually:")
            print(f"   schtasks /Run /TN {task_name}")
            print(f"\nTo delete it:")
            print(f"   schtasks /Delete /TN {task_name} /F")
            return True
        else:
            print(f"\n[ERROR] Failed to create scheduled task:")
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"\n[ERROR] Error creating scheduled task: {e}")
        return False

if __name__ == "__main__":
    print("=" * 70)
    print("Feature 3: Automated Scheduling Setup")
    print("=" * 70)
    print()
    
    success = create_scheduled_task()
    
    if success:
        print("\n" + "=" * 70)
        print("[OK] Setup Complete!")
        print("=" * 70)
        print("\nFeature 3 will now run automatically every day at 1:00 AM")
        print("No manual intervention required!")
    else:
        print("\n" + "=" * 70)
        print("[ERROR] Setup Failed")
        print("=" * 70)
        print("\nPlease run this script as Administrator")
