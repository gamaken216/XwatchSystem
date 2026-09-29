' XwatchSystem を黒い窓を出さずに実行する（タスクスケジューラ用）
' 2026-09-07 作成。GitHub Actions がCloudflareのbot判定で使えなくなったためローカル実行に移行。
WaitForDropbox
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd /c cd /d """ & Replace(WScript.ScriptFullName, WScript.ScriptName, "") & """ && python -X utf8 main.py", 0, False

' --- Dropboxの同期待ち（2026-09-28追加）---
' PC起動直後はDropboxより先にタスクが走り、他のPCが書いた .last_run が届く前に
' 「未送信」と判断して二重配信になる（2026-09-28にデスクトップPCで発生）。
' まず3分待ち、さらにDropboxが起動して5分経つまで待つ。最大20分で打ち切って実行する。
Sub WaitForDropbox()
    Dim wmi, dt, procs, p, t, oldest, waited
    WScript.Sleep 180000
    waited = 180
    Set wmi = GetObject("winmgmts:\\.\root\cimv2")
    Set dt = CreateObject("WbemScripting.SWbemDateTime")
    Do While waited < 1200
        oldest = Empty
        Set procs = wmi.ExecQuery("SELECT CreationDate FROM Win32_Process WHERE Name='Dropbox.exe'")
        For Each p In procs
            If Not IsNull(p.CreationDate) Then
                dt.Value = p.CreationDate
                t = dt.GetVarDate(True)
                If IsEmpty(oldest) Then
                    oldest = t
                ElseIf t < oldest Then
                    oldest = t
                End If
            End If
        Next
        If Not IsEmpty(oldest) Then
            If DateDiff("s", oldest, Now) >= 300 Then Exit Do
        End If
        WScript.Sleep 30000
        waited = waited + 30
    Loop
End Sub
