' XwatchSystem を黒い窓を出さずに実行する（タスクスケジューラ用）
' 2026-09-07 作成。GitHub Actions がCloudflareのbot判定で使えなくなったためローカル実行に移行。
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd /c cd /d """ & Replace(WScript.ScriptFullName, WScript.ScriptName, "") & """ && python -X utf8 main.py", 0, False
