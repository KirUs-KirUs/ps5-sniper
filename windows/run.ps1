# Один проход PS5 Sniper на этом ПК: обновить репозиторий, проверить Makler, отправить data/ в GitHub.
# Запускается Планировщиком задач (см. setup.ps1). Лог: logs\run.log
param([string]$Python = "python")

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
New-Item -ItemType Directory -Force (Join-Path $root "logs") | Out-Null
$log = Join-Path $root "logs\run.log"
$env:PYTHONIOENCODING = "utf-8"

function Write-Log($msg) { Add-Content -Path $log -Value $msg -Encoding UTF8 }

Write-Log ("`n=== " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + " ===")
git pull --rebase --autostash -q 2>&1 | ForEach-Object { Write-Log "git: $_" }
& $Python -m sniper.main 2>&1 | ForEach-Object { Write-Log "$_" }
Write-Log "sniper exit code: $LASTEXITCODE"

git add data 2>&1 | Out-Null
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    git commit -q -m ("data: update " + (Get-Date -Format "yyyy-MM-dd HH:mm")) 2>&1 | ForEach-Object { Write-Log "git: $_" }
    for ($i = 0; $i -lt 3; $i++) {
        git push -q 2>&1 | ForEach-Object { Write-Log "git: $_" }
        if ($LASTEXITCODE -eq 0) { Write-Log "pushed"; break }
        git pull --rebase -q 2>&1 | ForEach-Object { Write-Log "git: $_" }
    }
}

# держим лог небольшим
$lines = Get-Content $log -Encoding UTF8
if ($lines.Count -gt 3000) { $lines | Select-Object -Last 1500 | Set-Content $log -Encoding UTF8 }
