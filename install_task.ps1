$taskName = "Gleis"
$pythonExe = "c:\Users\kyangzhang\sbb-notifications\.venv\Scripts\python.exe"
$script = "c:\Users\kyangzhang\sbb-notifications\main.py"
$workDir = "c:\Users\kyangzhang\sbb-notifications"
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
$action = New-ScheduledTaskAction -Execute $pythonExe -Argument $script -WorkingDirectory $workDir
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Days 0)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description "Swiss transit arrival reminder" -RunLevel Limited
Write-Host "Task registered successfully."
