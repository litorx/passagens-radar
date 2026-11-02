# Agenda o radar de MILHAS no Windows (a cada 2 h, quando voce esta logado).
# Uso (PowerShell, na pasta do projeto):  .\windows\instalar_tarefa.ps1
$py   = (Get-Command python).Source
$repo = Split-Path -Parent $PSScriptRoot
$act  = New-ScheduledTaskAction -Execute $py -Argument "-m radar.scan_miles" -WorkingDirectory $repo
$trg  = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) -RepetitionInterval (New-TimeSpan -Hours 2)
$set  = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 40)
Register-ScheduledTask -TaskName "RadarMilhas" -Action $act -Trigger $trg -Settings $set -Force | Out-Null
Write-Host "Tarefa RadarMilhas criada (a cada 2 h)."
Write-Host "Defina antes: setx TELEGRAM_BOT_TOKEN ...  setx TELEGRAM_CHAT_ID ...  setx CONFIG_URL <link raw do data/config.json>"
Write-Host "Testar agora:  python -m radar.scan_miles --force --limit 2 --dry"
Write-Host "Remover:       Unregister-ScheduledTask -TaskName RadarMilhas -Confirm:`$false"
