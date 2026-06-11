# 有名人のX投稿監視システム（XwatchSystem）

## セッション開始時の必須手順：Notionの履歴を読む

このプロジェクトの過去セッション履歴はNotionデータベース「Claude Code セッションログ」に保存されている。
**セッション開始時、作業に入る前に必ず以下を実行すること：**

1. Notion MCPの `notion-search` で、データソース `collection://1b831064-a86c-440d-b6ab-8470fae25b9a`（Claude Code セッションログ）を対象に、このプロジェクト（有名人のX投稿監視システム / XwatchSystem）の直近セッションを検索する
2. 直近2〜3件のページを `notion-fetch` で読み、「未解決事項」「次のアクション」「決定事項」プロパティを確認する
3. 確認した内容（前回の続き・未解決事項）を最初の返答でユーザーに要約して伝えてから作業を始める

検索例: query「有名人のX投稿監視システム」、または直近日付フィルタ付きで検索。

## システム概要

- GitHub Actions（monitor.yml）で毎日自動実行されるX（Twitter）投稿監視システム
- リポジトリ: gamaken216/XwatchSystem
- 流れ: targets.json読み込み → X投稿収集（collector.py）→ Gemini分析（analyzer.py、モデルは gemini-2.5-flash-lite。2.0系は無料枠廃止のため使用不可）→ レポート生成（reporter.py）→ メール送信（sender.py）
- 収集履歴は `data/history_*.json` にローカル保存（重複検知用）。Notionとは無関係。

## 注意事項

- Geminiは無料枠のため、日次クォータ超過時は分析を即スキップして部分レポートを送る設計
- 全件0件のときは収集失敗とみなし管理者へアラートメールを送る
- X認証はcookie方式（GitHub Secretsに保存）。cookie失効が定期的な障害原因になる
