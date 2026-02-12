param(
    [string]$VBRServer = "localhost",
    [int]$Days = 30
)

$ErrorActionPreference = "Stop"

try {
    if (-not (Get-Module -ListAvailable -Name Veeam.Backup.PowerShell)) {
        throw "Veeam PowerShell module not installed"
    }
    
    Import-Module Veeam.Backup.PowerShell -Force -WarningAction SilentlyContinue
    Connect-VBRServer -Server $VBRServer -WarningAction SilentlyContinue
    
    $startDate = (Get-Date).AddDays(-$Days)
    
    $results = @()
    
    # Surgical Fetch 1: Restore Sessions
    # This avoids the hundreds of thousands of "Discovery" sessions
    $restoreSessions = Get-VBRRestoreSession | Where-Object { $_.CreationTime -ge $startDate }
    foreach ($session in $restoreSessions) {
        $results += @{
            sessionId = $session.Id.ToString()
            jobId = if ($session.JobId) { $session.JobId.ToString() } else { "none" }
            jobName = $session.JobName
            sessionType = "Restore"
            startTime = $session.CreationTime.ToString("yyyy-MM-ddTHH:mm:ssZ")
            endTime = if ($session.EndTime -ne [DateTime]::MinValue) { $session.EndTime.ToString("yyyy-MM-ddTHH:mm:ssZ") } else { $null }
            result = $session.Result.ToString()
        }
    }
    
    # Surgical Fetch 2: SureBackup Sessions
    $sbSessions = Get-VBRSureBackupSession | Where-Object { $_.CreationTime -ge $startDate }
    foreach ($session in $sbSessions) {
        $results += @{
            sessionId = $session.Id.ToString()
            jobId = if ($session.JobId) { $session.JobId.ToString() } else { "none" }
            jobName = $session.JobName
            sessionType = "SureBackup"
            startTime = $session.CreationTime.ToString("yyyy-MM-ddTHH:mm:ssZ")
            endTime = if ($session.EndTime -ne [DateTime]::MinValue) { $session.EndTime.ToString("yyyy-MM-ddTHH:mm:ssZ") } else { $null }
            result = $session.Result.ToString()
        }
    }
    
    $results | ConvertTo-Json -Depth 2
    Disconnect-VBRServer
}
catch {
    Write-Error "Historical session collection failed: $($_.Exception.Message)"
}
finally {
    # Silence any secondary errors on disconnect
    try { Disconnect-VBRServer } catch {}
}
