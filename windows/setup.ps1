# Настройка PS5 Sniper на этом ПК: секреты, зависимости, тестовое сообщение, задача в Планировщике.
# Запуск:  powershell -ExecutionPolicy Bypass -File windows\setup.ps1
# Другой интервал:  ... -File windows\setup.ps1 -IntervalMinutes 60
param([int]$IntervalMinutes = 20)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$envFile = Join-Path $root ".env"

# 1. Python
$py = (& python -c "import sys; print(sys.executable)").Trim()
Write-Host "Python: $py"

# 2. Секреты (файл .env не попадает в git)
if (-not (Test-Path $envFile)) {
    $token = Read-Host "Токен Telegram-бота (от @BotFather)"
    $chat = Read-Host "Ваш chat id (от @userinfobot)"
    $text = "TELEGRAM_BOT_TOKEN=$($token.Trim())`nTELEGRAM_CHAT_ID=$($chat.Trim())`n"
    [System.IO.File]::WriteAllText($envFile, $text, (New-Object System.Text.UTF8Encoding $false))
    Write-Host ".env создан"
} else {
    Write-Host ".env уже есть — оставляю (удалите файл, чтобы ввести заново)"
}

# 3. Зависимости
& $py -m pip install -q -r requirements.txt

# 4. Тестовое сообщение
$env:PYTHONIOENCODING = "utf-8"
& $py -c "from sniper.main import load_env, ROOT; load_env(ROOT / '.env'); import os; from sniper.notify import Telegram; Telegram(os.environ['TELEGRAM_BOT_TOKEN'], os.environ['TELEGRAM_CHAT_ID']).send_message('✅ PS5 Sniper: Telegram подключён')"
if ($LASTEXITCODE -ne 0) { throw "Telegram не принял сообщение: проверьте токен и chat id в .env и что вы нажали Start у бота" }
Write-Host "Тестовое сообщение отправлено в Telegram"

# 5. Задача в Планировщике (запуск скрыто, пропущенные запуски — сразу после включения ПК)
$runScript = Join-Path $root "windows\run.ps1"
$psArgs = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$runScript`" -Python `"$py`""
$action = New-ScheduledTaskAction -Execute "conhost.exe" -Argument "--headless powershell.exe $psArgs" -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 20) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName "PS5 Sniper" -Action $action -Trigger $trigger -Settings $settings `
    -Description "Проверка объявлений PS5 на makler.md" -Force | Out-Null

# 6. Команда /check в Telegram: задача раз в минуту ждёт сообщений бота ~50 с
$cmdArgs = "--headless `"$py`" -m sniper.commands"
$cmdAction = New-ScheduledTaskAction -Execute "conhost.exe" -Argument $cmdArgs -WorkingDirectory $root
$cmdTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 1)
$cmdSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 2) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName "PS5 Sniper Commands" -Action $cmdAction -Trigger $cmdTrigger -Settings $cmdSettings `
    -Description "Команда /check для бота PS5 Sniper" -Force | Out-Null

Write-Host ""
Write-Host "Команда /check в Telegram включена."
Write-Host "Готово: задача 'PS5 Sniper' будет запускаться каждые $IntervalMinutes мин. Первая проверка — через минуту."
Write-Host "Лог: $root\logs\run.log"
Write-Host "Остановить: Get-ScheduledTask -TaskName 'PS5 Sniper*' | Unregister-ScheduledTask -Confirm:`$false"
