' XwatchSystem を黒い窓を出さずに実行する（タスクスケジューラ用）
' 2026-09-07 作成。GitHub Actions がCloudflareのbot判定で使えなくなったためローカル実行に移行。
If Attempt() = 1 Then WaitForDropbox
RunWithRetry "cmd /c cd /d """ & Replace(WScript.ScriptFullName, WScript.ScriptName, "") & """", "python -X utf8 main.py"

' --- 失敗時の時間差リトライ・同時実行防止（2026-10-14追加）---
' Xの「検索欄がスピナーのまま」の詰まりは数時間で解ける（10/14は8:50失敗→10:50正常）。
' main.py が終了コード75（=やり直す価値あり）で終わったら、60分後・さらに120分後にもう一度走らせる。
' タスクの実行時間上限が2時間なので、待ちは自分自身を引数つきで別プロセスとして起動して引き継ぐ。
' 送信済みなら main.py が .last_run を見てスキップするので、二重配信にはならない。
' XwatchSystem と x_summary2 は同じXアカウントで読むため、同じPCでは同時に走らせない（%TEMP%\x_scrape.lock）。
Const RETRY_EXIT = 75

Function Attempt()
    Attempt = 1
    If WScript.Arguments.Count > 0 Then
        If IsNumeric(WScript.Arguments(0)) Then Attempt = CInt(WScript.Arguments(0))
    End If
End Function

Sub RunWithRetry(cmdPrefix, cmdMain)
    Dim n, waits, remain, rc, shell
    Set shell = CreateObject("WScript.Shell")
    waits = Array(0, 0, 60, 120)   ' 回目ごとの事前待ち（分）。1回目は0
    n = Attempt()
    If n > UBound(waits) Then Exit Sub
    If waits(n) > 0 Then WScript.Sleep waits(n) * 60000
    remain = UBound(waits) - n
    rc = RunLocked(cmdPrefix & " && set XRETRY_REMAIN=" & remain & "&& " & cmdMain)
    If rc = RETRY_EXIT And remain > 0 Then
        shell.Run "wscript.exe """ & WScript.ScriptFullName & """ " & (n + 1), 0, False
    End If
End Sub

Function RunLocked(cmd)
    Dim fso, shell, lockPath, f, waited, owned
    Set fso = CreateObject("Scripting.FileSystemObject")
    Set shell = CreateObject("WScript.Shell")
    lockPath = shell.ExpandEnvironmentStrings("%TEMP%") & "\x_scrape.lock"
    waited = 0
    owned = False
    Do
        If fso.FileExists(lockPath) Then
            ' 異常終了で残ったロックは90分で無効とみなす
            If DateDiff("n", fso.GetFile(lockPath).DateLastModified, Now) > 90 Then
                On Error Resume Next
                fso.DeleteFile lockPath, True
                On Error GoTo 0
            End If
        End If
        On Error Resume Next
        Set f = fso.CreateTextFile(lockPath, False)
        If Err.Number = 0 Then owned = True
        Err.Clear
        On Error GoTo 0
        If owned Then
            f.Write WScript.ScriptFullName
            f.Close
            Exit Do
        End If
        If waited >= 3600 Then Exit Do   ' 1時間待っても空かなければロック無しで走る
        WScript.Sleep 30000
        waited = waited + 30
    Loop
    RunLocked = shell.Run(cmd, 0, True)
    If owned Then
        On Error Resume Next
        fso.DeleteFile lockPath, True
        On Error GoTo 0
    End If
End Function

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
