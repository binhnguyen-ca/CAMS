# CAMS — snapshot tat ca marketer Crossian (DIM+FACT), day len GitHub. Task Scheduler goi 24 lan/ngay @ HH:05.
# Chay tay thu:  powershell -ExecutionPolicy Bypass -File scripts\run_snapshot.ps1
# (File ASCII khong dau de tranh loi encoding Windows PowerShell 5.1.)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

# Log moi lan chay vao logs/snapshot_YYYY-MM.log (logs/ trong .gitignore).
# Vi sao: task chay cua so an (WindowStyle Hidden) -> khong co log thi khong dieu tra
# duoc vi sao miss khung (vd 2026-06-10 miss 12-15h, 2026-06-11 miss 3-6h).
$logDir = Join-Path $repo "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
Start-Transcript -Path (Join-Path $logDir ("snapshot_{0:yyyy-MM}.log" -f (Get-Date))) -Append | Out-Null

try {
    Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm')] CAMS Snapshot"

    # 0) Lay code/config moi nhat. Best-effort. (cmd /c de stderr cua git khong bi
    #    PS 5.1 + ErrorActionPreference=Stop coi la loi terminating)
    cmd /c "git pull --rebase --autostash >nul 2>&1"
    if ($LASTEXITCODE -ne 0) { Write-Host "git pull bo qua (ma $LASTEXITCODE)." }

    # 1) Lam moi phien Grafana (tu dang nhap lai bang cookie Google neu het han)
    python scripts/refresh_session.py
    if ($LASTEXITCODE -ne 0) { Write-Host "Canh bao: lam moi phien khong thanh cong." }

    # 2) Snapshot DIM+FACT (tu doc snapshot_config.json; bo qua neu enabled=false).
    #    Retry 1 lan sau 60s: loi tam thoi (vd 401 do Grafana vua xoay session, DB busy)
    #    ma bo cuoc luon = MAT VINH VIEN khung gio nay (khong backfill duoc).
    python scripts/cams_snapshot.py
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Snapshot that bai (ma $LASTEXITCODE) -> thu lai sau 60s..."
        Start-Sleep -Seconds 60
        python scripts/refresh_session.py
        python scripts/cams_snapshot.py
        if ($LASTEXITCODE -ne 0) { throw "cams_snapshot.py that bai sau 2 lan (ma $LASTEXITCODE)" }
    }

    # 3) Commit + push neu co thay doi (pull-before-push de khong bi tu choi)
    git add data/campaigns.csv data/facts data/snapshot_config.json
    git diff --staged --quiet
    if ($LASTEXITCODE -ne 0) {
        git commit -m "snapshot: $(Get-Date -Format 'yyyy-MM-dd_HHmm')" | Out-Null
        cmd /c "git pull --rebase --autostash >nul 2>&1"
        cmd /c "git push 2>&1"
        if ($LASTEXITCODE -ne 0) { throw "git push that bai (ma $LASTEXITCODE)" }
        Write-Host "Da day snapshot len GitHub."
    } else {
        Write-Host "Khong co thay doi de day."
    }
} catch {
    Write-Host "LOI: $_"
    Stop-Transcript | Out-Null
    exit 1
}
Stop-Transcript | Out-Null
