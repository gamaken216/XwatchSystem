# X 有名人モニタリングシステム

X（旧Twitter）上の有名人に関する投稿を自動収集・AI分析し、HTMLレポートをメール配信するシステムです。

---

## 📁 ファイル構成

```
├── main.py          # メインスクリプト
├── collector.py     # ツイート収集（twikit）
├── analyzer.py      # AI分析（Gemini）
├── reporter.py      # HTMLレポート生成
├── sender.py        # メール送信（Gmail）
├── config.py        # 設定ファイル ⚠️ GitHubにあげない
├── targets.json     # 監視対象人物リスト
├── requirements.txt # 依存ライブラリ
└── .github/
    └── workflows/
        └── monitor.yml  # GitHub Actions設定
```

---

## 🚀 GitHub Actions セットアップ手順

### STEP 1: GitHubにリポジトリを作成してコードをプッシュ

1. [GitHub](https://github.com) にログインし、新しいリポジトリを作成（**Privateを推奨**）
2. ローカルでGitを初期化してプッシュ：

```bash
cd 有名人のX投稿監視システム
git init
git add .
git commit -m "初回コミット"
git remote add origin https://github.com/あなたのユーザー名/XwatchSystem.git
git push -u origin main
```

> ⚠️ `config.py` は `.gitignore` に含まれているので自動的に除外されます。

---

### STEP 2: GitHub Secrets に秘密情報を登録

リポジトリの **Settings → Secrets and variables → Actions → New repository secret** から以下を登録：

| Secret名 | 値の例 | 説明 |
|----------|--------|------|
| `GEMINI_API_KEY` | `AIzaSy...` | Google Gemini APIキー |
| `GMAIL_USER` | `xxx@gmail.com` | Gmailアドレス |
| `GMAIL_APP_PASSWORD` | `xxxx xxxx xxxx xxxx` | Gmailアプリパスワード |
| `X_COOKIES_JSON` | `{"auth_token":"...","ct0":"...","twid":"..."}` | XのCookie（JSON形式） |

**X_COOKIES_JSON の形式：**
```json
{"auth_token": "ここにauth_token", "ct0": "ここにct0", "twid": "ここにtwid"}
```

---

### STEP 3: スケジュールを確認・変更

`.github/workflows/monitor.yml` の `cron` 設定を変更することで実行タイミングを調整できます。

```yaml
schedule:
  # 毎朝9時（日本時間）
  - cron: '0 0 * * *'
```

**cron 設定例（日本時間）：**

| 内容 | cron設定（UTC） |
|------|----------------|
| 毎朝9時 | `0 0 * * *` |
| 毎朝8時 | `0 23 * * *` |
| 毎週月曜9時 | `0 0 * * 1` |
| 平日毎朝9時 | `0 0 * * 1-5` |

---

### STEP 4: 動作確認（手動実行）

1. GitHubのリポジトリページで **Actions** タブをクリック
2. **X モニタリング 自動実行** を選択
3. **Run workflow** ボタンをクリック
4. `テストモード` をONにしてメール送信なしで動作確認できます

---

## ⚙️ ローカルでの実行方法

```bash
# 依存ライブラリのインストール
pip install -r requirements.txt

# 日次レポート
python main.py

# 週次レポート
python main.py --weekly

# テスト実行（メール送信なし）
python main.py --test
```

---

## 📊 監視対象の追加・変更

`targets.json` を編集して監視対象を追加できます：

```json
{
  "targets": [
    {
      "id": "person_001",
      "name": "人物名",
      "keywords": ["キーワード1", "キーワード2"],
      "x_account": "@アカウント名",
      "exclude_keywords": [],
      "category": "カテゴリ",
      "recipients": ["送信先メール@example.com"],
      "enabled": true
    }
  ]
}
```
