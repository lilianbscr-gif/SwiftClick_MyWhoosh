# setup_scheduler.ps1
# Usage: .\scripts\setup_scheduler.ps1

$projectDir = "c:\Users\lilia\Documents\SwiftClick_MyWhoosh"
$psExe = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$logDir = Join-Path $projectDir "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -RestartCount 2 `
    -RestartInterval (New-TimeSpan -Minutes 10) `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable

$scoutScript = Join-Path $projectDir "scripts\run_scout.ps1"
$scoutArg = "-NonInteractive -ExecutionPolicy Bypass -File `"$scoutScript`""
$scoutAction = New-ScheduledTaskAction -Execute $psExe -Argument $scoutArg -WorkingDirectory $projectDir
$scoutTrigger = New-ScheduledTaskTrigger -Daily -At "08:00"

Register-ScheduledTask `
    -TaskName "SwiftClick-ResearchScout" `
    -TaskPath "\SwiftClick\" `
    -Action $scoutAction `
    -Trigger $scoutTrigger `
    -Settings $settings `
    -Description "Research Scout quotidien SwiftClick_MyWhoosh" `
    -Force | Out-Null

Write-Host "OK SwiftClick-ResearchScout : daily at 08:00"

$reviewScript = Join-Path $projectDir "scripts\run_review.ps1"
$reviewArg = "-NonInteractive -ExecutionPolicy Bypass -File `"$reviewScript`""
$reviewAction = New-ScheduledTaskAction -Execute $psExe -Argument $reviewArg -WorkingDirectory $projectDir
$reviewTrigger = New-ScheduledTaskTrigger -Weekly -WeeksInterval 1 -DaysOfWeek Sunday -At "09:00"

Register-ScheduledTask `
    -TaskName "SwiftClick-ResearchReview" `
    -TaskPath "\SwiftClick\" `
    -Action $reviewAction `
    -Trigger $reviewTrigger `
    -Settings $settings `
    -Description "Research Review dimanche SwiftClick_MyWhoosh" `
    -Force | Out-Null

Write-Host "OK SwiftClick-ResearchReview : Sunday at 09:00"
Write-Host ""
Write-Host "Check  : Get-ScheduledTask -TaskPath '\SwiftClick\'"
Write-Host "Test   : Start-ScheduledTask -TaskName 'SwiftClick-ResearchScout' -TaskPath '\SwiftClick\'"
