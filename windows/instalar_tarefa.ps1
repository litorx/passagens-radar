# Instala 2 tarefas no Windows (rodam quando voce esta logado):
#   RadarBot    a cada 2 min : le seus comandos do Telegram (resposta quase imediata; sem janela)
#   RadarMilhas a cada 2 h   : Smiles/LATAM em milhas (Chrome fora da tela)
# Uso (PowerShell, na pasta do projeto):  .\windows\instalar_tarefa.ps1 [-Python C:\caminho\python.exe]
# Segredos: data_local\.env (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID). Nada de setx.
param([string]$Python = "")
if (-not $Python) {
  $cands = @("$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
             "$env:LOCALAPPDATA\Python\pythoncore-3.14-64\python.exe",
             "$env:LOCALAPPDATA\Python\pythoncore-3.13-64\python.exe")
  $Python = $cands | Where-Object { Test-Path $_ } | Select-Object -First 1
  if (-not $Python) { $Python = (Get-Command python).Source }
}
$PythonW = $Python -replace 'python\.exe$', 'pythonw.exe'
if (-not (Test-Path $PythonW)) { $PythonW = $Python }
$repo = Split-Path -Parent $PSScriptRoot
$set  = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 40)

$a1 = New-ScheduledTaskAction -Execute $PythonW -Argument "-m radar.poll_local" -WorkingDirectory $repo
$t1 = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 2)
Register-ScheduledTask -TaskName "RadarBot" -Action $a1 -Trigger $t1 -Settings $set -Force | Out-Null

$a2 = New-ScheduledTaskAction -Execute $PythonW -Argument "-m radar.scan_miles" -WorkingDirectory $repo
$t2 = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(3) -RepetitionInterval (New-TimeSpan -Hours 2)
Register-ScheduledTask -TaskName "RadarMilhas" -Action $a2 -Trigger $t2 -Settings $set -Force | Out-Null

Write-Host "Tarefas criadas: RadarBot (2 min) e RadarMilhas (2 h), usando $PythonW"
Write-Host "Remover:  Unregister-ScheduledTask -TaskName RadarBot,RadarMilhas -Confirm:`$false"
