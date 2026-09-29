# XwatchSystem（有名人のX投稿監視システム）

> セッション開始時のNotion履歴確認は親フォルダの `GAI\CLAUDE.md` の必須手順に従うこと（自動で読み込まれる）。
> **注意：** 2026-06-11にフォルダ名を「有名人のX投稿監視システム」から「XwatchSystem」に変更した。それ以前のNotionセッションログは旧名で記録されているため、過去履歴を検索するときは「XwatchSystem」と「有名人のX投稿監視システム」の両方で検索すること。

## システム概要

- X（Twitter）投稿監視システム。**2026-09-07から各PCのタスクスケジューラ「XwatchSystem-Daily」でローカル実行**（`run_silent.vbs` を起動）。GitHub ActionsのIPが `x.com/search` でCloudflareのbot判定を受けるため移行した。monitor.yml の cron はコメントアウト済み（`workflow_dispatch` のみ残置）
- リポジトリ: gamaken216/XwatchSystem
- 流れ: targets.json読み込み → X投稿収集（collector.py）→ Gemini分析（analyzer.py、モデルは gemini-2.5-flash-lite。2.0系は無料枠廃止のため使用不可）→ レポート生成（reporter.py）→ メール送信（sender.py）
- **Geminiのモデル名は main.py のハードコードが効く。** config.py にも `GEMINI_MODEL` があるが `get_config()` が上書きするため使われない（config.py 側だけ直しても反映されない）
- 収集履歴は `data/history_*.json` にローカル保存（重複検知用）。Notionとは無関係。
- 3台で走るため `.last_run`（Dropbox共有）で1日1回に制限している

## 注意事項

- Geminiは無料枠のため、日次クォータ超過時は分析を即スキップして部分レポートを送る設計
- 全件0件のときは収集失敗とみなし**管理者（matsmoto.norihito@gmail.com）のみ**へアラートメールを送る。日次レポートだけが pr_all@ascom-inc.jp にも届く
- X認証はcookie方式（ローカルは config.py、Actions用にGitHub Secretsにも保存）。cookie失効が定期的な障害原因になる
- **収集失敗の切り分け手順：** ①`logs/run_*.log` のサイズを見る（成功日は約5.4KB、失敗日は約2.3KB）②`logs/debug/*.png` を見る — ログイン画面ならCookie失効／「人間であることを確認します」ならbot判定／スピナーのままなら一時的な詰まり ③`Get-ScheduledTaskInfo -TaskName XwatchSystem-Daily` の `LastTaskResult`（0なら起動自体は成功）
- **3連続失敗で打ち切ったあと、30秒待って未収集ぶんをもう一巡試す**（2026-09-09に追加）。先頭3件がたまたま詰まっただけで残り15件が全滅した実績があるため。Cookie失効時は回復不能なので再試行しない
- ターゲット別の収集結果はログファイルにも記録される（`print()` は run_silent.vbs 経由だと捨てられるため）
