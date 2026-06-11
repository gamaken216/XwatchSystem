# XwatchSystem（有名人のX投稿監視システム）

> セッション開始時のNotion履歴確認は親フォルダの `GAI\CLAUDE.md` の必須手順に従うこと（自動で読み込まれる）。
> **注意：** 2026-06-11にフォルダ名を「有名人のX投稿監視システム」から「XwatchSystem」に変更した。それ以前のNotionセッションログは旧名で記録されているため、過去履歴を検索するときは「XwatchSystem」と「有名人のX投稿監視システム」の両方で検索すること。

## システム概要

- GitHub Actions（monitor.yml）で毎日自動実行されるX（Twitter）投稿監視システム
- リポジトリ: gamaken216/XwatchSystem
- 流れ: targets.json読み込み → X投稿収集（collector.py）→ Gemini分析（analyzer.py、モデルは gemini-2.5-flash-lite。2.0系は無料枠廃止のため使用不可）→ レポート生成（reporter.py）→ メール送信（sender.py）
- 収集履歴は `data/history_*.json` にローカル保存（重複検知用）。Notionとは無関係。

## 注意事項

- Geminiは無料枠のため、日次クォータ超過時は分析を即スキップして部分レポートを送る設計
- 全件0件のときは収集失敗とみなし管理者へアラートメールを送る
- X認証はcookie方式（GitHub Secretsに保存）。cookie失効が定期的な障害原因になる
