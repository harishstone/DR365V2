# ============================================================================
# DR365V2 - Complete Scheduled Task Setup
# ============================================================================
# This script creates/updates all 6 feature tasks with the new schedule:
# F1: 10:45 PM | F2: 11:00 PM | F3: 11:15 PM
# F4: 11:30 PM | F5: 11:45 PM | F6: 11:50 PM
# ============================================================================

# Requires Administrator privileges
if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Warning "This script requires Administrator privileges. Please run as Administrator."
    exit 1
}

$pythonPath = "C:\Users\Administrator\AppData\Local\Programs\Python\Python314\python.exe"
$baseDir = "C:\DR365\DR365V2\src"

# Task definitions: Name, Script Path, Time
$tasks = @(
    @{Name="DR365 - Feature 1 Health";     Script="$baseDir\feature1\feature1.py"; Time="22:45"},
    @{Name="DR365 - Feature 2 Capacity";   Script="$baseDir\feature2\feature2.py"; Time="23:00"},
    @{Name="DR365 - Feature 3 Efficiency"; Script="$baseDir\feature3\feature3.py"; Time="23:15"},
    @{Name="DR365 - Feature 4 Recovery";   Script="$baseDir\feature4\feature4.py"; Time="23:30"},
    @{Name="DR365 - Feature 5 Risk";       Script="$baseDir\feature5\feature5.py"; Time="23:45"},
    @{Name="DR365 - Feature 6 Remediation"; Script="$baseDir\feature6\feature6.py"; Time="23:50"}
)

Write-Host "`n============================================================================" -ForegroundColor Cyan
Write-Host "DR365V2 Scheduled Task Setup" -ForegroundColor Cyan
Write-Host "============================================================================`n" -ForegroundColor Cyan

foreach ($task in $tasks) {
    $taskName = $task.Name
    $scriptPath = $task.Script
    $startTime = $task.Time
    
    Write-Host "Processing: $taskName (Start: $startTime)" -ForegroundColor Yellow
    
    # Check if task already exists
    $existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    
    if ($existingTask) {
        Write-Host "  - Task exists. Removing old version..." -ForegroundColor Gray
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    }
    
    # Create action
    $action = New-ScheduledTaskAction -Execute $pythonPath -Argument $scriptPath
    
    # Create trigger (Daily at specified time)
    $trigger = New-ScheduledTaskTrigger -Daily -At $startTime
    
    # Create settings
    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -RunOnlyIfNetworkAvailable `
        -ExecutionTimeLimit (New-TimeSpan -Hours 1)
    
    # Create principal (run as current user)
    $principal = New-ScheduledTaskPrincipal -UserId "Administrator" -RunLevel Highest
    
    # Register the task
    Register-ScheduledTask `
        -TaskName $taskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Principal $principal `
        -Description "DR365V2 automated analysis task" | Out-Null
    
    Write-Host "  - Task created successfully!" -ForegroundColor Green
}

Write-Host "`n============================================================================" -ForegroundColor Cyan
Write-Host "Summary of Scheduled Tasks" -ForegroundColor Cyan
Write-Host "============================================================================`n" -ForegroundColor Cyan

Get-ScheduledTask | Where-Object {$_.TaskName -like "DR365 - Feature*"} | ForEach-Object {
    $info = Get-ScheduledTaskInfo -TaskName $_.TaskName
    $trigger = $_.Triggers[0]
    
    Write-Host "$($_.TaskName)" -ForegroundColor White
    Write-Host "  State: $($_.State)" -ForegroundColor $(if ($_.State -eq 'Ready') {'Green'} else {'Red'})
    Write-Host "  Next Run: $($info.NextRunTime)" -ForegroundColor Cyan
    Write-Host "  Last Run: $($info.LastRunTime)" -ForegroundColor Gray
    Write-Host "  Last Result: $($info.LastTaskResult) $(if ($info.LastTaskResult -eq 0) {'(Success)'} else {'(Failed)'})" -ForegroundColor $(if ($info.LastTaskResult -eq 0) {'Green'} else {'Red'})
    Write-Host ""
}

Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "============================================================================`n" -ForegroundColor Cyan
Write-Host "All 6 features are now scheduled to run daily:" -ForegroundColor White
Write-Host "  F1 (Health):       10:45 PM" -ForegroundColor Gray
Write-Host "  F2 (Capacity):     11:00 PM" -ForegroundColor Gray
Write-Host "  F3 (Efficiency):   11:15 PM" -ForegroundColor Gray
Write-Host "  F4 (Recovery):     11:30 PM" -ForegroundColor Gray
Write-Host "  F5 (Risk):         11:45 PM" -ForegroundColor Gray
Write-Host "  F6 (Remediation):  11:50 PM" -ForegroundColor Gray
Write-Host ""
