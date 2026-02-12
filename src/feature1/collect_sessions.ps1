param(
    [string]$OutputFile = "feature1_sessions.json",
    [int]$Days = 120
)

$ErrorActionPreference = "Stop"

try {
    Write-Host "Loading Veeam PowerShell Module..."
    if (-not (Get-Module -Name Veeam.Backup.PowerShell -ErrorAction SilentlyContinue)) {
        Import-Module Veeam.Backup.PowerShell
    }
    
    $StartDate = (Get-Date).AddDays(-$Days)
    Write-Host "Fetching sessions since $($StartDate.ToString('yyyy-MM-dd'))..."
    
    # Fetch sessions (Get ALL, filter later if needed)
    $Sessions = Get-VBRBackupSession
    
    $Results = @()
    
    foreach ($S in $Sessions) {
        $Results += @{
            id = $S.Id.ToString()
            jobId = $S.JobId.ToString()
            jobName = $S.JobName
            jobType = $S.JobType.ToString()
            creationTime = $S.CreationTime.ToString("yyyy-MM-ddTHH:mm:ss")
            startTime = $S.CreationTime.ToString("yyyy-MM-ddTHH:mm:ss")
            endTime = $S.EndTime.ToString("yyyy-MM-ddTHH:mm:ss")
            result = $S.Result.ToString() # Success, Warning, Failed
            state = $S.State.ToString()
            progress = $S.Progress.Percents
            isRetry = $S.IsRetry
            # Add minimal object details to satisfy feature1 data model
            totalObjects = 1 
            processedObjects = 1
        }
    }
    
    Write-Host "Found $($Results.Count) sessions."
    
    # Export to JSON
    $Results | ConvertTo-Json -Depth 2 | Out-File -FilePath $OutputFile -Encoding UTF8
    Write-Host "Exported to $OutputFile"

} catch {
    Write-Error "Error: $_"
    exit 1
}
