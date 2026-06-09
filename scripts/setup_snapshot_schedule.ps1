# Tao tac vu "CAMS Snapshot" chay 24 khung/ngay @ HH:05 (gio VN cua may).
# Chay 1 lan (khong can admin):  powershell -ExecutionPolicy Bypass -File scripts\setup_snapshot_schedule.ps1
$ErrorActionPreference = "Stop"

$hours = 0..23
$triggers = foreach ($h in $hours) {
    New-ScheduledTaskTrigger -Daily -At ("{0:00}:05" -f $h)
}

$wrapper = Join-Path $PSScriptRoot "run_snapshot.ps1"
$pwsh = (Get-Command powershell.exe).Source
$arg = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$wrapper`""
$action = New-ScheduledTaskAction -Execute $pwsh -Argument $arg
# StartWhenAvailable: PC tat luc do -> chay bu khi bat lai.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 50)

Register-ScheduledTask -TaskName "CAMS Snapshot" -Action $action -Trigger $triggers `
    -Settings $settings -Description "CAMS: snapshot all-marketer Crossian (DIM+FACT) 24 khung/ngay @ HH:05" -Force | Out-Null

Write-Host "Da dat 'CAMS Snapshot' chay 24 khung/ngay @ HH:05 (gio VN)."
Write-Host "Go bo:  Unregister-ScheduledTask -TaskName 'CAMS Snapshot' -Confirm:`$false"
