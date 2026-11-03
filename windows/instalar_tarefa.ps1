# Agenda o radar de MILHAS no Windows (a cada 2 h, quando voce esta logado).
# Uso (PowerShell, na pasta do projeto):  .\windows\instalar_tarefa.ps1 [-Python C:\caminho\python.exe] [-Horas 2]
# Segredos ficam em data_local\.env (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, CONFIG_URL); nada de setx.
param(
  [string]$Python = "",
  [int]$Horas = 2
)
if (-not $Python) {
  $cands = @("$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
             "$env:LOCALAPPDATA\Python\pythoncore-3.14-64\python.exe",
             "$env:LOCALAPPDATA\Python\pythoncore-3.13-64\python.exe")
  $Python = $cands | Where-Object { Test-Path $_ } | Select-Object -First 1
  if (-not $Python) { $Python = (Get-Command python).Source }
}
$repo = Split-Path -Parent $PSScriptRoot
$act  = New-ScheduledTaskAction -Execute $Python -Argument "-m radar.scan_miles" -WorkingDirectory $repo
$trg  = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) -RepetitionInterval (New-TimeSpan -Hours $Horas)
$set  = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 40)
Register-ScheduledTask -TaskName "RadarMilhas" -Action $act -Trigger $trg -Settings $set -Force | Out-Null
Write-Host "Tarefa RadarMilhas criada: a cada $Horas h, usando $Python"
Write-Host "Testar agora:  & '$Python' -m radar.scan_miles --force --limit 2 --dry"
Write-Host "Remover:       Unregister-ScheduledTask -TaskName RadarMilhas -Confirm:`$false"
