# Tao tac vu "CAMS Snapshot" chay 24 khung/ngay @ HH:55 (gio VN cua may) + chay bu khi logon.
# Chup tai :55 = CHOT khung gio ke tiep (vd 14:55 -> khung 15:00 = chot ca ngay Anchorage,
# chi hut 5 phut cuoi). App hien thi khung = gio chup + 5 phut (transform.vn_label).
# Chay 1 lan (khong can admin):  powershell -ExecutionPolicy Bypass -File scripts\setup_snapshot_schedule.ps1
$ErrorActionPreference = "Stop"

$hours = 0..23
$triggers = @(foreach ($h in $hours) {
    New-ScheduledTaskTrigger -Daily -At ("{0:00}:55" -f $h)
})

# Catch-up khi logon: task dang ky kieu Interactive -> sau khi Windows Update tu reboot
# (vd 3h sang 2026-06-11), KHONG ai logon thi task khong chay duoc va cac khung bi bo
# qua luon (StartWhenAvailable khong bu lai duoc). Trigger nay chay ngay khi logon lai
# de cuu khung gan nhat. Delay 90s cho mang/profile on dinh.
$logon = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$logon.Delay = "PT90S"
$triggers += $logon

$wrapper = Join-Path $PSScriptRoot "run_snapshot.ps1"
$pwsh = (Get-Command powershell.exe).Source
$arg = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$wrapper`""
$action = New-ScheduledTaskAction -Execute $pwsh -Argument $arg
# StartWhenAvailable : lo khung (may ban) -> chay bu khi ranh.
# WakeToRun          : danh thuc may tu Modern Standby de chay khung — may ngu S0 idle
#                      la nguyen nhan miss 12-15h VN ngay 2026-06-10.
# AllowStartIfOnBatteries + DontStopIfGoingOnBatteries: mac dinh Windows CHAN task khi
#                      chay pin -> tat chan cho chac (may ban hien tai khong co pin).
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 50)

Register-ScheduledTask -TaskName "CAMS Snapshot" -Action $action -Trigger $triggers `
    -Settings $settings -Description "CAMS: snapshot all-marketer Crossian (DIM+FACT) 24 khung/ngay @ HH:55 + catch-up logon" -Force | Out-Null

Write-Host "Da dat 'CAMS Snapshot': 24 khung/ngay @ HH:55 + chay bu khi logon; WakeToRun=ON."
Write-Host "Go bo:  Unregister-ScheduledTask -TaskName 'CAMS Snapshot' -Confirm:`$false"
