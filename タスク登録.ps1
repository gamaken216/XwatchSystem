# XwatchSystem の日次タスクをこのPCに登録する（3台それぞれで1回だけ実行する）
# 2026-09-07 作成。GitHub Actions がCloudflareのbot判定で使えなくなったためローカル実行に移行。
# 実行時刻はPCごとにずらす。二重配信は .last_run（Dropbox共有）でも防いでいるが、
# 同時刻に走ると同期が間に合わず2通出るおそれがあるため。

$dir = Split-Path -Parent $MyInvocation.MyCommand.Path

# このPCの実行時刻を選ぶ（すでに他のPCが使っている時刻は避ける）
$time = Read-Host "実行時刻を入力 (例 08:30 / デスクトップPC=08:30, ミニノート=09:30, でかノート=10:30)"
if (-not $time) { $time = "08:30" }

$action   = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$dir\run_silent.vbs`"" -WorkingDirectory $dir
$trigger  = New-ScheduledTaskTrigger -Daily -At $time
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 2) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName "XwatchSystem-Daily" -Action $action -Trigger $trigger -Settings $settings -Description "アスコム著者X投稿監視の日次レポート。PCが落ちていた日は起動後にできるだけ早く実行される。" -Force | Out-Null

Get-ScheduledTask -TaskName "XwatchSystem-Daily" | Select-Object TaskName, State, @{n='次回';e={($_ | Get-ScheduledTaskInfo).NextRunTime}} | Format-Table -AutoSize
Write-Host ""
Write-Host "登録しました。Enterで閉じます。"
Read-Host
