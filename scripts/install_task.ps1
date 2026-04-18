$taskName = "Gleis"
$workDir = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $workDir ".venv\Scripts\python.exe"
$script = Join-Path $workDir "main.py"
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
$action = New-ScheduledTaskAction -Execute $pythonExe -Argument $script -WorkingDirectory $workDir
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Days 0)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description "Swiss transit arrival reminder" -RunLevel Limited
Write-Host "Task registered successfully."
