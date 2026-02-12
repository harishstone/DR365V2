# ============================================================================
# Feature 3: Storage Efficiency Data Retrieval via PowerShell
# ============================================================================
# 
# Purpose: Retrieve deduplication and compression ratios using Veeam PowerShell
# Reason: REST API v1.0 doesn't expose these fields, but PowerShell does
# 
# NEW DOCS Reference: Feature 03 - Section 4.2 (Data Collection)
# ============================================================================

param(
    [Parameter(Mandatory=$false)]
    [int]$DaysBack = 30,
    
    [Parameter(Mandatory=$false)]
    [string]$OutputPath = "efficiency_data.json"
)

# Import Veeam PowerShell Module (PowerShell 7 compatible)
Write-Host "Loading Veeam PowerShell module..." -ForegroundColor Cyan
try {
    $veeamModule = "C:\Program Files\Veeam\Backup and Replication\Console\Veeam.Backup.PowerShell.dll"
    Import-Module $veeamModule -ErrorAction Stop -WarningAction SilentlyContinue
    Write-Host "✅ Veeam PowerShell module loaded" -ForegroundColor Green
} catch {
    Write-Host "❌ Failed to load Veeam PowerShell module: $_" -ForegroundColor Red
    exit 1
}

# Calculate date range
$endDate = Get-Date
$startDate = $endDate.AddDays(-$DaysBack)

Write-Host "`n📊 Fetching backup sessions from $($startDate.ToString('yyyy-MM-dd')) to $($endDate.ToString('yyyy-MM-dd'))" -ForegroundColor Cyan

# Get all backup jobs
$jobs = Get-VBRJob | Where-Object { $_.JobType -eq "Backup" }
Write-Host "Found $($jobs.Count) backup jobs" -ForegroundColor Yellow

# Initialize results array
$results = @()
$totalSessions = 0
$sessionsWithData = 0
$sessionsWithoutData = 0

# Process each job
foreach ($job in $jobs) {
    Write-Host "`nProcessing job: $($job.Name)" -ForegroundColor White
    
    # Get sessions for this job within date range
    $sessions = Get-VBRBackupSession | Where-Object {
        $_.JobId -eq $job.Id -and
        $_.CreationTime -ge $startDate -and
        $_.CreationTime -le $endDate
    } | Sort-Object CreationTime -Descending
    
    Write-Host "  Found $($sessions.Count) sessions" -ForegroundColor Gray
    $totalSessions += $sessions.Count
    
    foreach ($session in $sessions) {
        try {
            # Get efficiency metrics from BackupStats (NOT GetDetails!)
            $stats = $session.BackupStats
            
            if ($stats) {
                # Extract efficiency metrics
                $dedupe = $stats.DedupRatio
                $compression = $stats.CompressRatio
                
                # Only include if we have valid data
                if ($dedupe -and $compression -and $dedupe -gt 0 -and $compression -gt 0) {
                    $sessionData = [PSCustomObject]@{
                        SessionId = $session.Id.ToString()
                        JobId = $job.Id.ToString()
                        JobName = $job.Name
                        JobType = $job.JobType.ToString()
                        CreationTime = $session.CreationTime.ToString("yyyy-MM-ddTHH:mm:ssZ")
                        EndTime = $session.EndTime.ToString("yyyy-MM-ddTHH:mm:ssZ")
                        Result = $session.Result.ToString()
                        State = $session.State.ToString()
                        
                        # Efficiency Metrics (the key data!)
                        DedupeRatio = [double]$dedupe
                        CompressionRatio = [double]$compression
                        CombinedRatio = [double]($dedupe * $compression)
                        
                        # Additional metrics for context
                        BackupSizeGB = [math]::Round($stats.DataSize / 1GB, 2)
                        TransferredSizeGB = [math]::Round($stats.BackupSize / 1GB, 2)
                        DurationMinutes = [math]::Round($session.Progress.Duration.TotalMinutes, 2)
                    }
                    
                    $results += $sessionData
                    $sessionsWithData++
                } else {
                    $sessionsWithoutData++
                }
            } else {
                $sessionsWithoutData++
            }
        } catch {
            Write-Host "  ⚠️ Error processing session $($session.Id): $_" -ForegroundColor Yellow
            $sessionsWithoutData++
        }
    }
}

# Summary
Write-Host "`n" + ("=" * 70) -ForegroundColor Cyan
Write-Host "EFFICIENCY DATA COLLECTION SUMMARY" -ForegroundColor Cyan
Write-Host ("=" * 70) -ForegroundColor Cyan
Write-Host "Total Sessions Scanned: $totalSessions" -ForegroundColor White
Write-Host "Sessions with Efficiency Data: $sessionsWithData" -ForegroundColor Green
Write-Host "Sessions without Data: $sessionsWithoutData" -ForegroundColor Yellow
Write-Host ("=" * 70) -ForegroundColor Cyan

# Export to JSON
if ($results.Count -gt 0) {
    $jsonOutput = $results | ConvertTo-Json -Depth 10
    $jsonOutput | Out-File -FilePath $OutputPath -Encoding UTF8
    
    Write-Host "`n✅ Exported $($results.Count) sessions to: $OutputPath" -ForegroundColor Green
    
    # Show sample statistics
    $avgDedupe = ($results | Measure-Object -Property DedupeRatio -Average).Average
    $avgCompression = ($results | Measure-Object -Property CompressionRatio -Average).Average
    $avgCombined = ($results | Measure-Object -Property CombinedRatio -Average).Average
    
    Write-Host "`n📈 AVERAGE EFFICIENCY METRICS:" -ForegroundColor Cyan
    Write-Host "  Deduplication Ratio: $([math]::Round($avgDedupe, 2))x" -ForegroundColor White
    Write-Host "  Compression Ratio: $([math]::Round($avgCompression, 2))x" -ForegroundColor White
    Write-Host "  Combined Ratio: $([math]::Round($avgCombined, 2))x" -ForegroundColor White
    Write-Host "  Storage Reduction: $([math]::Round((1 - 1/$avgCombined) * 100, 1))%" -ForegroundColor Green
    
} else {
    Write-Host "`n❌ No efficiency data found!" -ForegroundColor Red
    Write-Host "This may indicate:" -ForegroundColor Yellow
    Write-Host "  1. No backup sessions in the specified date range" -ForegroundColor Yellow
    Write-Host "  2. Sessions lack efficiency statistics" -ForegroundColor Yellow
    Write-Host "  3. Veeam version doesn't support these metrics" -ForegroundColor Yellow
}

Write-Host "`n✅ Script completed" -ForegroundColor Green
