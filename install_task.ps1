 = "SBB-Not"
 = "c:\Users\kyangzhang\sbb-notifications\.venv\Scripts\python.exe"
 = "c:\Users\kyangzhang\sbb-notifications\main.py"
 = "c:\Users\kyangzhang\sbb-notifications"
Unregister-ScheduledTask -TaskName  -Confirm:$false -ErrorAction SilentlyContinue
 = New-ScheduledTaskAction -Execute  -Argument  -WorkingDirectory 
 = New-ScheduledTaskTrigger -AtLogOn -User kyangzhang
 = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Days 0)
Register-ScheduledTask -TaskName  -Action  -Trigger  -Settings  -Description "Swiss transit arrival reminder" -RunLevel Limited
Write-Host "Task registered successfully."
