# CAMS — snapshot tat ca marketer Crossian (DIM+FACT), day len GitHub. Task Scheduler goi 24 lan/ngay @ HH:05.
# Chay tay thu:  powershell -ExecutionPolicy Bypass -File scripts\run_snapshot.ps1
# (File ASCII khong dau de tranh loi encoding Windows PowerShell 5.1.)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm')] CAMS Snapshot"

# 0) Lay code/config moi nhat. Best-effort.
try { git pull --rebase --autostash 2>&1 | Out-Null } catch { Write-Host "git pull bo qua: $_" }

# 1) Lam moi phien Grafana (tu dang nhap lai bang cookie Google neu het han)
python scripts/refresh_session.py
if ($LASTEXITCODE -ne 0) { Write-Host "Canh bao: lam moi phien khong thanh cong." }

# 2) Snapshot DIM+FACT (tu doc snapshot_config.json; bo qua neu enabled=false)
python scripts/cams_snapshot.py
if ($LASTEXITCODE -ne 0) { throw "cams_snapshot.py that bai (ma $LASTEXITCODE)" }

# 3) Commit + push neu co thay doi (pull-before-push de khong bi tu choi)
git add data/campaigns.csv data/facts data/snapshot_config.json
git diff --staged --quiet
if ($LASTEXITCODE -ne 0) {
    git commit -m "snapshot: $(Get-Date -Format 'yyyy-MM-dd_HHmm')" | Out-Null
    try { git pull --rebase --autostash 2>&1 | Out-Null } catch { Write-Host "git pull truoc push bo qua: $_" }
    git push
    Write-Host "Da day snapshot len GitHub."
} else {
    Write-Host "Khong co thay doi de day."
}
