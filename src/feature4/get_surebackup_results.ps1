param(
    [string]$VBRServer = "localhost",
    [int]$TimeoutSeconds = 300
)

# Set error preference
$ErrorActionPreference = "Stop"

try {
    # Connect to Veeam Backup Server
    if (-not (Get-Module -ListAvailable -Name Veeam.Backup.PowerShell)) {
        throw "Veeam PowerShell module not installed"
    }
    
    Import-Module Veeam.Backup.PowerShell -Force
    
    Connect-VBRServer -Server $VBRServer
    
    # Get all SureBackup jobs
    $sureBackupJobs = Get-VBRSureBackupJob
    
    $results = @()
    
    foreach ($job in $sureBackupJobs) {
        # Get latest session for this job
        $sessions = Get-VBRSureBackupSession -Job $job | Sort-Object CreationTime -Descending | Select-Object -First 1
        
        if ($sessions) {
            $session = $sessions[0]
            
            # Get VM results from session
            $vmResults = Get-VBRSureBackupVmFromSession -Session $session
            
            foreach ($vmResult in $vmResults) {
                $result = @{
                    vmId = $vmResult.Vm.Id
                    vmName = $vmResult.Vm.Name
                    testResult = switch ($vmResult.State) {
                        "Success" { "Success" }
                        "Warning" { "Partial" }
                        "Failed" { "Failed" }
                        default { "Unknown" }
                    }
                    bootTime = if ($vmResult.BootTime.TotalMilliseconds) { 
                        [int]$vmResult.BootTime.TotalMilliseconds 
                    } else { 0 }
                    verifiedDrives = ($vmResult.DriveResults | Where-Object { $_.VerificationResult -eq "Success" }).Count
                    failedDrives = ($vmResult.DriveResults | Where-Object { $_.VerificationResult -ne "Success" }).Count
                }
                
                $results += $result
            }
        }
    }
    
    # Output as JSON
    $results | ConvertTo-Json -Depth 4
    
    # Disconnect
    Disconnect-VBRServer
    
    exit 0
}
catch {
    Write-Error "SureBackup collection failed: $($_.Exception.Message)"
    exit 1
}
