"""
X有名人モニタリングシステム - Web管理画面
==========================================
Flask ベースのローカル管理画面。
対象人物の追加・編集・削除、設定変更、テスト実行が可能。

起動方法: python web_admin.py
ブラウザで http://localhost:5001 にアクセス
"""
import asyncio
import json
import os
import sys
import io
import uuid
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, url_for, flash, jsonify

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TARGETS_FILE = os.path.join(SCRIPT_DIR, "targets.json")
SETTINGS_FILE = os.path.join(SCRIPT_DIR, "settings.json")
REPORTS_DIR = os.path.join(SCRIPT_DIR, "docs", "reports")
WORKFLOW_FILE = os.path.join(SCRIPT_DIR, ".github", "workflows", "monitor.yml")

app = Flask(__name__)
app.secret_key = "x_monitoring_admin_2026"


# === データ操作 ===

def load_targets():
    if os.path.exists(TARGETS_FILE):
        with open(TARGETS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"targets": []}


def save_targets(data):
    with open(TARGETS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    _git_push_targets()


def _git_push_targets():
    """targets.json をGitHubに自動commit & pushする"""
    import subprocess
    try:
        env = os.environ.copy()
        env["GIT_ASKPASS"] = "echo"
        env["GIT_TERMINAL_PROMPT"] = "0"
        subprocess.run(
            ["git", "-C", SCRIPT_DIR, "add", "targets.json"],
            check=True, env=env, capture_output=True,
        )
        result = subprocess.run(
            ["git", "-C", SCRIPT_DIR, "commit", "-m",
             f"targets.json 更新 {datetime.now():%Y-%m-%d %H:%M}"],
            env=env, capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if result.returncode == 0:
            subprocess.run(
                ["git", "-C", SCRIPT_DIR, "push", "origin", "master"],
                check=True, env=env, capture_output=True,
                text=True, encoding="utf-8", errors="replace",
            )
            print("  ✅ targets.json をGitHubにpushしました")
        elif "nothing to commit" in (result.stdout or ""):
            print("  ℹ targets.json に変更なし（push不要）")
        else:
            print(f"  ⚠ git commit失敗: {result.stderr}")
    except subprocess.CalledProcessError as e:
        print(f"  ⚠ GitHub pushに失敗: {e}")
    except Exception as e:
        print(f"  ⚠ git操作エラー: {e}")


def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    # config.py からフォールバック読み込み
    try:
        from config import (X_COOKIES, GEMINI_API_KEY, GEMINI_MODEL,
                            GMAIL_USER, GMAIL_APP_PASSWORD,
                            MAX_TWEETS_PER_PERSON, SEARCH_INTERVAL_SEC)
        return {
            "x_cookies": X_COOKIES,
            "gemini_api_key": GEMINI_API_KEY,
            "gemini_model": GEMINI_MODEL,
            "gmail_user": GMAIL_USER,
            "gmail_app_password": GMAIL_APP_PASSWORD,
            "max_tweets": MAX_TWEETS_PER_PERSON,
            "search_interval": SEARCH_INTERVAL_SEC,
        }
    except:
        return {
            "x_cookies": {"auth_token": "", "ct0": "", "twid": ""},
            "gemini_api_key": "",
            "gemini_model": "gemini-2.5-flash",
            "gmail_user": "",
            "gmail_app_password": "",
            "max_tweets": 100,
            "search_interval": 5,
        }


def save_settings(data):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    # config.py も同期更新
    config_path = os.path.join(SCRIPT_DIR, "config.py")
    config_content = f'''"""
X有名人モニタリングシステム - 設定ファイル
Web管理画面から自動生成 ({datetime.now():%Y-%m-%d %H:%M})
"""

X_COOKIES = {json.dumps(data["x_cookies"], ensure_ascii=False, indent=4)}

GEMINI_API_KEY = "{data["gemini_api_key"]}"
GEMINI_MODEL = "{data.get("gemini_model", "gemini-2.5-flash")}"

GMAIL_USER = "{data["gmail_user"]}"
GMAIL_APP_PASSWORD = "{data["gmail_app_password"]}"

MAX_TWEETS_PER_PERSON = {data.get("max_tweets", 100)}
SEARCH_INTERVAL_SEC = {data.get("search_interval", 5)}
REPORT_LANGUAGE = "ja"
'''
    with open(config_path, "w", encoding="utf-8") as f:
        f.write(config_content)


def get_recent_reports(limit=10):
    if not os.path.exists(REPORTS_DIR):
        return []
    files = sorted(
        [f for f in os.listdir(REPORTS_DIR) if f.endswith(".html")],
        reverse=True
    )
    return files[:limit]


# === HTMLテンプレート ===

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>X有名人モニタリング - 管理画面</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Hiragino Sans', 'Yu Gothic', 'Meiryo', sans-serif; background: #f0f2f5; color: #1a1a2e; }

/* ナビ */
.navbar { background: #1E2761; color: white; padding: 16px 24px; display: flex; align-items: center; justify-content: space-between; }
.navbar h1 { font-size: 20px; }
.navbar .nav-links a { color: #E8C547; text-decoration: none; margin-left: 20px; font-size: 14px; }
.navbar .nav-links a:hover { text-decoration: underline; }

/* コンテナ */
.container { max-width: 960px; margin: 24px auto; padding: 0 16px; }

/* フラッシュメッセージ */
.flash { padding: 12px 16px; border-radius: 8px; margin-bottom: 16px; font-size: 14px; }
.flash.success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
.flash.error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
.flash.info { background: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb; }

/* カード */
.card { background: white; border-radius: 12px; padding: 24px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.card h2 { font-size: 18px; color: #1E2761; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #E8C547; }
.card h3 { font-size: 16px; color: #4A6FA5; margin: 16px 0 8px; }

/* フォーム */
.form-group { margin-bottom: 14px; }
.form-group label { display: block; font-size: 13px; font-weight: bold; color: #555; margin-bottom: 4px; }
.form-group input, .form-group select, .form-group textarea {
    width: 100%; padding: 10px 12px; border: 1px solid #ddd; border-radius: 6px;
    font-size: 14px; font-family: inherit; }
.form-group input:focus, .form-group textarea:focus { outline: none; border-color: #4A6FA5; box-shadow: 0 0 0 2px rgba(74,111,165,0.15); }
.form-group .hint { font-size: 12px; color: #888; margin-top: 2px; }
.form-row { display: flex; gap: 12px; }
.form-row .form-group { flex: 1; }

/* ボタン */
.btn { display: inline-block; padding: 10px 20px; border: none; border-radius: 6px; font-size: 14px;
       cursor: pointer; text-decoration: none; font-weight: bold; transition: 0.2s; }
.btn-primary { background: #1E2761; color: white; }
.btn-primary:hover { background: #2a3578; }
.btn-success { background: #27AE60; color: white; }
.btn-success:hover { background: #219a52; }
.btn-danger { background: #E74C3C; color: white; }
.btn-danger:hover { background: #c0392b; }
.btn-outline { background: white; color: #1E2761; border: 1px solid #1E2761; }
.btn-outline:hover { background: #f0f2f5; }
.btn-sm { padding: 6px 12px; font-size: 12px; }
.btn-group { display: flex; gap: 8px; margin-top: 16px; }

/* 対象人物リスト */
.target-list { list-style: none; }
.target-item { display: flex; align-items: center; justify-content: space-between; padding: 14px 16px;
               border: 1px solid #e5e7eb; border-radius: 8px; margin-bottom: 8px; transition: 0.2s; }
.target-item:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.target-item.disabled { opacity: 0.5; }
.target-info h4 { font-size: 16px; color: #1a1a2e; margin-bottom: 4px; }
.target-info .meta { font-size: 12px; color: #888; }
.target-info .keywords { font-size: 12px; color: #4A6FA5; margin-top: 4px; }
.badge { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: bold; }
.badge-category { background: #EBF5FB; color: #4A6FA5; }
.badge-enabled { background: #d4edda; color: #155724; }
.badge-disabled { background: #f8d7da; color: #721c24; }

/* レポート一覧 */
.report-list { list-style: none; }
.report-list li { padding: 8px 0; border-bottom: 1px solid #f0f0f0; }
.report-list li:last-child { border-bottom: none; }
.report-list a { color: #4A6FA5; text-decoration: none; }
.report-list a:hover { text-decoration: underline; }

/* タブ */
.tabs { display: flex; gap: 0; margin-bottom: 24px; border-bottom: 2px solid #e5e7eb; }
.tab { padding: 10px 20px; cursor: pointer; font-size: 14px; font-weight: bold; color: #888;
       border-bottom: 2px solid transparent; margin-bottom: -2px; text-decoration: none; }
.tab.active { color: #1E2761; border-bottom-color: #E8C547; }
.tab:hover { color: #1E2761; }

/* 並び替えボタン */
.btn-move { display:block; width:24px; height:20px; text-align:center; line-height:20px; font-size:10px;
            color:#1E2761; text-decoration:none; border-radius:4px; cursor:pointer; }
.btn-move:hover { background:#e8f1fd; }
.btn-move-disabled { color:#ddd; cursor:default; }
.btn-move-disabled:hover { background:transparent; }
</style>
</head>
<body>

<div class="navbar">
    <h1>X有名人モニタリング</h1>
    <div class="nav-links">
        <a href="{{ url_for('index') }}">対象人物</a>
        <a href="{{ url_for('schedule_page') }}">スケジュール</a>
        <a href="{{ url_for('settings_page') }}">設定</a>
        <a href="{{ url_for('reports_page') }}">レポート</a>
    </div>
</div>

<div class="container">
    {% with messages = get_flashed_messages(with_categories=true) %}
    {% if messages %}
        {% for category, message in messages %}
        <div class="flash {{ category }}">{{ message }}</div>
        {% endfor %}
    {% endif %}
    {% endwith %}

    {% block content %}{% endblock %}
</div>

</body>
</html>
"""

# === 対象人物一覧 ===
INDEX_PAGE = """
{% extends "base" %}
{% block content %}
<div class="card">
    <h2>対象人物一覧</h2>
    <a href="{{ url_for('add_target') }}" class="btn btn-primary" style="margin-bottom:16px;">＋ 新しい対象人物を追加</a>

    <p style="font-size:12px;color:#888;margin-bottom:12px;">※ 上にあるほど優先的にAI分析されます。API枠が不足した場合、下位の項目がスキップされます。</p>

    {% if targets %}
    <ul class="target-list">
        {% for t in targets %}
        <li class="target-item {{ 'disabled' if not t.enabled }}">
            <div style="display:flex;flex-direction:column;gap:2px;margin-right:12px;">
                {% if not loop.first %}
                <a href="{{ url_for('move_target', target_id=t.id, direction='up') }}" class="btn-move" title="上へ">▲</a>
                {% else %}
                <span class="btn-move btn-move-disabled">▲</span>
                {% endif %}
                <span style="text-align:center;font-size:11px;color:#888;">{{ loop.index }}</span>
                {% if not loop.last %}
                <a href="{{ url_for('move_target', target_id=t.id, direction='down') }}" class="btn-move" title="下へ">▼</a>
                {% else %}
                <span class="btn-move btn-move-disabled">▼</span>
                {% endif %}
            </div>
            <div class="target-info" style="flex:1;">
                <h4>
                    {{ t.name }}
                    <span class="badge badge-category">{{ t.category }}</span>
                    {% if t.enabled %}
                    <span class="badge badge-enabled">有効</span>
                    {% else %}
                    <span class="badge badge-disabled">無効</span>
                    {% endif %}
                </h4>
                <div class="keywords">キーワード: {{ t.keywords | join(', ') }}</div>
                <div class="meta">
                    {% if t.client and t.client != 'default' %}クライアント: <strong>{{ t.client }}</strong> | {% endif %}
                    {% if t.x_account %}アカウント: {{ t.x_account }} | {% endif %}
                    配信先: {{ t.recipients | join(', ') if t.recipients else '未設定' }}
                </div>
            </div>
            <div>
                <a href="{{ url_for('edit_target', target_id=t.id) }}" class="btn btn-outline btn-sm">編集</a>
                <a href="{{ url_for('toggle_target', target_id=t.id) }}" class="btn btn-outline btn-sm">
                    {{ '無効にする' if t.enabled else '有効にする' }}
                </a>
                <a href="{{ url_for('delete_target', target_id=t.id) }}" class="btn btn-danger btn-sm"
                   onclick="return confirm('{{ t.name }} を削除しますか？');">削除</a>
            </div>
        </li>
        {% endfor %}
    </ul>
    {% else %}
    <p style="color:#888; padding:20px 0;">対象人物が登録されていません。「新しい対象人物を追加」から登録してください。</p>
    {% endif %}
</div>

<div class="card">
    <h2>手動実行</h2>
    <div class="btn-group" id="run-buttons">
        <button class="btn btn-outline" onclick="runTask('test')">テスト実行（メール送信なし）</button>
        <button class="btn btn-success" onclick="runTask('daily')">日次レポート実行</button>
        <button class="btn btn-primary" onclick="runTask('weekly')">週次レポート実行</button>
    </div>
    <div id="run-progress" style="display:none; margin-top:16px;">
        <div style="display:flex; align-items:center; gap:10px; padding:16px; background:#EBF5FB; border-radius:8px;">
            <div class="spinner"></div>
            <span id="run-status" style="font-size:14px; color:#1E2761;">実行中...</span>
        </div>
    </div>
    <div id="run-result" style="display:none; margin-top:16px;"></div>
</div>

<style>
.spinner { width:20px; height:20px; border:3px solid #E5E7EB; border-top-color:#1E2761; border-radius:50%; animation:spin 0.8s linear infinite; }
@keyframes spin { to { transform:rotate(360deg); } }
</style>

<script>
async function runTask(mode) {
    const buttons = document.getElementById('run-buttons');
    const progress = document.getElementById('run-progress');
    const status = document.getElementById('run-status');
    const result = document.getElementById('run-result');
    const labels = {test:'テスト実行', daily:'日次レポート', weekly:'週次レポート'};

    buttons.querySelectorAll('button').forEach(b => b.disabled = true);
    progress.style.display = 'block';
    result.style.display = 'none';
    status.textContent = labels[mode] + ' を実行中... しばらくお待ちください';

    try {
        const res = await fetch('/run_async', {
            method: 'POST',
            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
            body: 'mode=' + mode
        });
        const data = await res.json();

        if (data.success) {
            progress.style.display = 'none';
            result.style.display = 'block';
            let html = '<div style="padding:16px; background:#d4edda; border-radius:8px; color:#155724;">';
            html += '<strong>✅ ' + labels[mode] + ' が完了しました！</strong><br>';
            html += '<span style="font-size:13px;">' + data.message + '</span>';
            if (data.report) {
                html += '<br><a href="/reports/' + data.report + '" target="_blank" style="color:#155724; font-weight:bold;">📄 レポートを見る</a>';
            }
            html += '</div>';
            result.innerHTML = html;
        } else {
            progress.style.display = 'none';
            result.style.display = 'block';
            result.innerHTML = '<div style="padding:16px; background:#f8d7da; border-radius:8px; color:#721c24;"><strong>❌ エラー</strong><br>' + data.message + '</div>';
        }
    } catch(e) {
        progress.style.display = 'none';
        result.style.display = 'block';
        result.innerHTML = '<div style="padding:16px; background:#f8d7da; border-radius:8px; color:#721c24;"><strong>❌ 通信エラー</strong><br>' + e.message + '</div>';
    }
    buttons.querySelectorAll('button').forEach(b => b.disabled = false);
}
</script>
{% endblock %}
"""

# === 対象人物 追加/編集 ===
TARGET_FORM_PAGE = """
{% extends "base" %}
{% block content %}
<div class="card">
    <h2>{{ '対象人物を編集' if edit_mode else '新しい対象人物を追加' }}</h2>
    <form method="post">
        <div class="form-group">
            <label>表示名 *</label>
            <input type="text" name="name" value="{{ target.name }}" required placeholder="例: 大谷翔平">
        </div>

        <div class="form-group">
            <label>検索キーワード *（カンマ区切りで複数入力）</label>
            <input type="text" name="keywords" value="{{ target.keywords | join(', ') }}" required
                   placeholder="例: 大谷翔平, Shohei Ohtani, おおたにしょうへい">
            <div class="hint">表記ゆれを含めて複数指定すると精度が上がります</div>
        </div>

        <div class="form-row">
            <div class="form-group">
                <label>Xアカウント（任意）</label>
                <input type="text" name="x_account" value="{{ target.x_account }}" placeholder="例: @shaboreveal">
                <div class="hint">@メンション付きツイートも収集する場合に指定</div>
            </div>
            <div class="form-group">
                <label>カテゴリ</label>
                <input type="text" name="category" value="{{ target.category }}" placeholder="例: スポーツ選手">
            </div>
        </div>

        <div class="form-row">
            <div class="form-group">
                <label>クライアントID（まとめ送信用）</label>
                <input type="text" name="client" value="{{ target.client or 'default' }}" placeholder="例: ascom">
                <div class="hint">同じIDを持つターゲットは1通のメールにまとめて送信されます</div>
            </div>
        </div>

        <div class="form-group">
            <label>除外キーワード（カンマ区切り、任意）</label>
            <input type="text" name="exclude_keywords" value="{{ target.exclude_keywords | join(', ') }}"
                   placeholder="例: 同姓同名の別人に関するキーワード">
            <div class="hint">ノイズとなるツイートを除外するためのキーワード</div>
        </div>

        <div class="form-group">
            <label>レポート配信先メールアドレス（カンマ区切り）</label>
            <input type="text" name="recipients" value="{{ target.recipients | join(', ') }}"
                   placeholder="例: report@example.com, client@example.com">
        </div>

        <div class="form-group">
            <label>
                <input type="checkbox" name="enabled" {{ 'checked' if target.enabled }}>
                モニタリングを有効にする
            </label>
        </div>

        <div class="btn-group">
            <button type="submit" class="btn btn-primary">{{ '更新' if edit_mode else '追加' }}</button>
            <a href="{{ url_for('index') }}" class="btn btn-outline">キャンセル</a>
        </div>
    </form>
</div>
{% endblock %}
"""

# === 設定ページ ===
SETTINGS_PAGE = """
{% extends "base" %}
{% block content %}
<div class="card">
    <h2>システム設定</h2>
    <form method="post" action="{{ url_for('save_settings_page') }}">

        <h3>X（Twitter）認証</h3>
        <div class="form-group">
            <label>auth_token</label>
            <input type="text" name="auth_token" value="{{ settings.x_cookies.auth_token }}">
        </div>
        <div class="form-group">
            <label>ct0</label>
            <input type="text" name="ct0" value="{{ settings.x_cookies.ct0 }}">
        </div>
        <div class="form-group">
            <label>twid</label>
            <input type="text" name="twid" value="{{ settings.x_cookies.twid }}">
        </div>

        <h3>Google Gemini API</h3>
        <div class="form-row">
            <div class="form-group">
                <label>APIキー</label>
                <input type="text" name="gemini_api_key" value="{{ settings.gemini_api_key }}">
            </div>
            <div class="form-group">
                <label>モデル</label>
                <input type="text" name="gemini_model" value="{{ settings.gemini_model }}">
                <div class="hint">例: gemini-2.5-flash, gemini-2.0-flash-lite</div>
            </div>
        </div>

        <h3>Gmail配信</h3>
        <div class="form-row">
            <div class="form-group">
                <label>Gmailアドレス</label>
                <input type="text" name="gmail_user" value="{{ settings.gmail_user }}">
            </div>
            <div class="form-group">
                <label>アプリパスワード</label>
                <input type="password" name="gmail_app_password" value="{{ settings.gmail_app_password }}">
            </div>
        </div>

        <h3>収集設定</h3>
        <div class="form-row">
            <div class="form-group">
                <label>対象人物あたりの最大取得件数</label>
                <input type="number" name="max_tweets" value="{{ settings.max_tweets }}">
            </div>
            <div class="form-group">
                <label>検索間隔（秒）</label>
                <input type="number" name="search_interval" value="{{ settings.search_interval }}">
                <div class="hint">レート制限回避用。5秒以上を推奨</div>
            </div>
        </div>

        <div class="btn-group">
            <button type="submit" class="btn btn-primary">設定を保存</button>
            <button type="button" class="btn btn-success" onclick="testConnection()">接続テスト</button>
        </div>
    </form>
</div>

<div id="test-results" class="card" style="display:none;">
    <h2>接続テスト結果</h2>
    <div id="test-output" style="white-space:pre-line; font-size:14px;"></div>
</div>

<script>
async function testConnection() {
    const el = document.getElementById('test-results');
    const out = document.getElementById('test-output');
    el.style.display = 'block';
    out.textContent = 'テスト中...';
    try {
        const res = await fetch('{{ url_for("test_connection") }}', {method: 'POST'});
        const data = await res.json();
        out.textContent = data.results.join('\\n');
    } catch(e) {
        out.textContent = 'エラー: ' + e.message;
    }
}
</script>
{% endblock %}
"""

# === スケジュールページ ===
SCHEDULE_PAGE = """
{% extends "base" %}
{% block content %}
<div class="card">
    <h2>配信スケジュール設定</h2>
    <form method="post" action="{{ url_for('save_schedule') }}">

        <h3>配信頻度</h3>
        <div style="display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap;">
            {% for val, label, desc in [('daily','毎日','日次レポート'),('weekly','週1回','週次レポート'),('both','両方','毎日＋週次'),('manual','手動のみ','自動配信なし')] %}
            <label style="flex:1;min-width:100px;border:2px solid {% if current_freq == val %}#1E2761{% else %}#ddd{% endif %};border-radius:10px;padding:14px;text-align:center;cursor:pointer;background:{% if current_freq == val %}#EBF5FB{% else %}#fff{% endif %};">
                <input type="radio" name="freq" value="{{ val }}" {% if current_freq == val %}checked{% endif %} style="display:none;" onchange="updateURL('freq', this.value)">
                <div style="font-size:20px;margin-bottom:6px;">{% if val=='daily' %}📅{% elif val=='weekly' %}📆{% elif val=='both' %}🗓{% else %}⏸{% endif %}</div>
                <div style="font-weight:700;font-size:14px;">{{ label }}</div>
                <div style="font-size:11px;color:#888;">{{ desc }}</div>
            </label>
            {% endfor %}
        </div>

        {% if current_freq != 'manual' %}
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px;">
            {% if current_freq in ['daily','both'] %}
            <div class="form-group">
                <label>📅 日次レポート 配信時刻（日本時間）</label>
                <select name="daily_hour" onchange="updateURL('daily_hour', this.value)">
                    {% for h in range(24) %}
                    <option value="{{ h }}" {% if h == daily_hour %}selected{% endif %}>{{ h }}時</option>
                    {% endfor %}
                </select>
            </div>
            {% endif %}
            {% if current_freq in ['weekly','both'] %}
            <div class="form-group">
                <label>📆 週次レポート 配信曜日</label>
                <select name="weekly_day" onchange="updateURL('weekly_day', this.value)">
                    {% for v, n in [(1,'月曜日'),(2,'火曜日'),(3,'水曜日'),(4,'木曜日'),(5,'金曜日'),(6,'土曜日'),(0,'日曜日')] %}
                    <option value="{{ v }}" {% if v == weekly_day %}selected{% endif %}>{{ n }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="form-group">
                <label>📆 週次レポート 配信時刻（日本時間）</label>
                <select name="weekly_hour" onchange="updateURL('weekly_hour', this.value)">
                    {% for h in range(24) %}
                    <option value="{{ h }}" {% if h == weekly_hour %}selected{% endif %}>{{ h }}時</option>
                    {% endfor %}
                </select>
            </div>
            {% endif %}
        </div>
        {% endif %}

        <div style="background:#fffbeb;border:1px solid #fde68a;border-radius:8px;padding:12px 16px;margin-bottom:16px;font-size:13px;color:#92400e;">
            {{ schedule_preview }}
        </div>

        <div class="btn-group">
            <button type="button" class="btn btn-primary" onclick="saveYML()">💾 monitor.yml に保存</button>
        </div>
    </form>
</div>

<div class="card" style="margin-top:20px;">
    <h2>📧 レポート送信先</h2>

    <p style="font-size:13px;color:#666;margin-bottom:16px;">クライアント単位で送信先を設定します。同じクライアントのターゲットには同じ送信先でレポートが届きます。<br>カンマ区切りで複数指定できます。</p>
    <form method="post" action="{{ url_for('save_recipients') }}">
        {% for info in client_info %}
        <div class="form-group" style="margin-bottom:16px;">
            <label>{{ info.client }}（{{ info.count }}件のターゲット）</label>
            <textarea name="client_{{ info.client }}" rows="2" style="width:100%;font-size:14px;" placeholder="例: user1@example.com, user2@example.com">{{ info.recipients }}</textarea>
        </div>
        {% endfor %}
        <div class="btn-group">
            <button type="submit" class="btn btn-primary">💾 送信先を保存</button>
        </div>
    </form>
</div>

<script>
function updateURL(key, value) {
    const url = new URL(window.location.href);
    url.searchParams.set(key, value);
    window.location.href = url.toString();
}
function saveYML() {
    fetch('/save_yml', {method: 'POST'})
        .then(r => r.json())
        .then(d => alert(d.success ? '✅ ' + d.message : '❌ ' + d.message))
        .catch(e => alert('❌ エラー: ' + e.message));
}
</script>
{% endblock %}
"""

# === レポートページ ===
REPORTS_PAGE = """
{% extends "base" %}
{% block content %}
<div class="card">
    <h2>生成済みレポート</h2>
    {% if reports %}
    <ul class="report-list">
        {% for r in reports %}
        <li>
            <a href="{{ url_for('view_report', filename=r) }}" target="_blank">{{ r }}</a>
        </li>
        {% endfor %}
    </ul>
    {% else %}
    <p style="color:#888; padding:20px 0;">レポートがまだ生成されていません。</p>
    {% endif %}
</div>
{% endblock %}
"""


# === Jinjaテンプレート登録 ===
from jinja2 import BaseLoader, TemplateNotFound

class InlineLoader(BaseLoader):
    templates = {
        "base": HTML_TEMPLATE,
        "index": INDEX_PAGE,
        "target_form": TARGET_FORM_PAGE,
        "settings": SETTINGS_PAGE,
        "schedule": SCHEDULE_PAGE,
        "reports": REPORTS_PAGE,
    }
    def get_source(self, environment, template):
        if template in self.templates:
            source = self.templates[template]
            return source, template, lambda: True
        raise TemplateNotFound(template)

app.jinja_loader = InlineLoader()


# === ルーティング ===

@app.route("/")
def index():
    data = load_targets()
    return render_template_string(
        '{% extends "index" %}', targets=data.get("targets", [])
    )


@app.route("/add", methods=["GET", "POST"])
def add_target():
    if request.method == "POST":
        data = load_targets()
        new_target = {
            "id": f"target_{uuid.uuid4().hex[:8]}",
            "name": request.form.get("name", "").strip(),
            "keywords": [k.strip() for k in request.form.get("keywords", "").split(",") if k.strip()],
            "x_account": request.form.get("x_account", "").strip(),
            "exclude_keywords": [k.strip() for k in request.form.get("exclude_keywords", "").split(",") if k.strip()],
            "category": request.form.get("category", "").strip(),
            "client": request.form.get("client", "default").strip() or "default",
            "recipients": [r.strip() for r in request.form.get("recipients", "").split(",") if r.strip()],
            "enabled": "enabled" in request.form,
        }
        data["targets"].append(new_target)
        save_targets(data)
        flash(f"✅ 「{new_target['name']}」を追加しました", "success")
        return redirect(url_for("index"))

    empty_target = {
        "name": "", "keywords": [], "x_account": "", "exclude_keywords": [],
        "category": "", "recipients": [], "enabled": True,
    }
    return render_template_string(
        '{% extends "target_form" %}', target=empty_target, edit_mode=False
    )


@app.route("/edit/<target_id>", methods=["GET", "POST"])
def edit_target(target_id):
    data = load_targets()
    target = next((t for t in data["targets"] if t["id"] == target_id), None)
    if not target:
        flash("対象人物が見つかりません", "error")
        return redirect(url_for("index"))

    if request.method == "POST":
        target["name"] = request.form.get("name", "").strip()
        target["keywords"] = [k.strip() for k in request.form.get("keywords", "").split(",") if k.strip()]
        target["x_account"] = request.form.get("x_account", "").strip()
        target["exclude_keywords"] = [k.strip() for k in request.form.get("exclude_keywords", "").split(",") if k.strip()]
        target["category"] = request.form.get("category", "").strip()
        target["client"] = request.form.get("client", "default").strip() or "default"
        target["recipients"] = [r.strip() for r in request.form.get("recipients", "").split(",") if r.strip()]
        target["enabled"] = "enabled" in request.form
        save_targets(data)
        flash(f"✅ 「{target['name']}」を更新しました", "success")
        return redirect(url_for("index"))

    return render_template_string(
        '{% extends "target_form" %}', target=target, edit_mode=True
    )


@app.route("/move/<target_id>/<direction>")
def move_target(target_id, direction):
    data = load_targets()
    targets = data["targets"]
    idx = next((i for i, t in enumerate(targets) if t["id"] == target_id), None)
    if idx is not None:
        if direction == "up" and idx > 0:
            targets[idx], targets[idx - 1] = targets[idx - 1], targets[idx]
        elif direction == "down" and idx < len(targets) - 1:
            targets[idx], targets[idx + 1] = targets[idx + 1], targets[idx]
        save_targets(data)
    return redirect(url_for("index"))


@app.route("/delete/<target_id>")
def delete_target(target_id):
    data = load_targets()
    target = next((t for t in data["targets"] if t["id"] == target_id), None)
    if target:
        data["targets"] = [t for t in data["targets"] if t["id"] != target_id]
        save_targets(data)
        flash(f"🗑 「{target['name']}」を削除しました", "info")
    return redirect(url_for("index"))


@app.route("/toggle/<target_id>")
def toggle_target(target_id):
    data = load_targets()
    target = next((t for t in data["targets"] if t["id"] == target_id), None)
    if target:
        target["enabled"] = not target["enabled"]
        save_targets(data)
        status = "有効" if target["enabled"] else "無効"
        flash(f"✅ 「{target['name']}」を{status}にしました", "success")
    return redirect(url_for("index"))


@app.route("/schedule", methods=["GET", "POST"])
def schedule_page():
    freq = request.values.get("freq", "daily")
    daily_hour = int(request.values.get("daily_hour", 7))
    weekly_day = int(request.values.get("weekly_day", 1))
    weekly_hour = int(request.values.get("weekly_hour", 7))

    days = ["日", "月", "火", "水", "木", "金", "土"]
    if freq == "daily":
        preview = f"📅 毎日 {daily_hour}時 に日次レポートを送信します"
    elif freq == "weekly":
        preview = f"📆 毎週{days[weekly_day]}曜日 {weekly_hour}時 に週次レポートを送信します"
    elif freq == "both":
        preview = f"📅 毎日 {daily_hour}時 に日次＋📆 毎週{days[weekly_day]}曜日 {weekly_hour}時 に週次レポートを送信します"
    else:
        preview = "⏸ 自動配信なし。GitHub Actionsから手動で実行できます"

    app.config["SCHEDULE"] = {
        "freq": freq, "daily_hour": daily_hour,
        "weekly_day": weekly_day, "weekly_hour": weekly_hour
    }

    settings = load_settings()
    report_recipients = settings.get("report_recipients", "")

    # クライアント別の送信先を集計
    targets_data = load_targets()
    client_recipients = {}
    client_target_count = {}
    for t in targets_data.get("targets", []):
        c = t.get("client", "default")
        if c not in client_recipients:
            client_recipients[c] = list(t.get("recipients", []))
            client_target_count[c] = 0
        client_target_count[c] += 1
    client_info = [
        {"client": c, "recipients": ", ".join(client_recipients[c]), "count": client_target_count[c]}
        for c in sorted(client_recipients.keys())
    ]

    return render_template_string(
        '{% extends "schedule" %}',
        current_freq=freq, daily_hour=daily_hour,
        weekly_day=weekly_day, weekly_hour=weekly_hour,
        schedule_preview=preview,
        report_recipients=report_recipients,
        client_info=client_info
    )


@app.route("/save_schedule", methods=["POST"])
def save_schedule():
    return redirect(url_for("schedule_page",
        freq=request.form.get("freq", "daily"),
        daily_hour=request.form.get("daily_hour", 7),
        weekly_day=request.form.get("weekly_day", 1),
        weekly_hour=request.form.get("weekly_hour", 7),
    ))


@app.route("/save_recipients", methods=["POST"])
def save_recipients():
    data = load_targets()
    # クライアント別の送信先をフォームから取得して全ターゲットに反映
    updated_clients = set()
    for key, value in request.form.items():
        if key.startswith("client_"):
            client_name = key[len("client_"):]
            recipients = [r.strip() for r in value.split(",") if r.strip()]
            for t in data["targets"]:
                if t.get("client", "default") == client_name:
                    t["recipients"] = recipients
            updated_clients.add(client_name)
    save_targets(data)
    flash(f"✅ 送信先を保存しました（{', '.join(sorted(updated_clients))}）", "success")
    return redirect(url_for("schedule_page"))


@app.route("/save_yml", methods=["POST"])
def save_yml():
    s = app.config.get("SCHEDULE", {"freq": "daily", "daily_hour": 7, "weekly_day": 1, "weekly_hour": 7})
    freq = s["freq"]
    daily_utc = (s["daily_hour"] - 9 + 24) % 24
    weekly_utc = (s["weekly_hour"] - 9 + 24) % 24
    weekly_day = s["weekly_day"]

    if freq == "daily":
        schedule_block = f"  schedule:\n    - cron: '0 {daily_utc} * * *'"
    elif freq == "weekly":
        schedule_block = f"  schedule:\n    - cron: '0 {weekly_utc} * * {weekly_day}'"
    elif freq == "both":
        schedule_block = f"  schedule:\n    - cron: '0 {daily_utc} * * *'\n    - cron: '0 {weekly_utc} * * {weekly_day}'"
    else:
        schedule_block = "  # 自動スケジュールなし（手動実行のみ）"

    yml = f"""name: X モニタリング 自動実行

on:
{schedule_block}

  workflow_dispatch:
    inputs:
      report_type:
        description: 'レポートタイプ'
        required: true
        default: 'daily'
        type: choice
        options:
          - daily
          - weekly
      test_mode:
        description: 'テストモード（メール送信しない）'
        required: false
        default: false
        type: boolean

jobs:
  run-monitor:
    runs-on: ubuntu-latest
    timeout-minutes: 30

    steps:
      - name: リポジトリをチェックアウト
        uses: actions/checkout@v4

      - name: Python 3.11 セットアップ
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: 依存ライブラリのインストール
        run: pip install -r requirements.txt

      - name: Playwright インストール
        run: playwright install chromium

      - name: 日次レポート実行
        if: github.event_name == 'schedule' || (github.event_name == 'workflow_dispatch' && github.event.inputs.report_type == 'daily' && github.event.inputs.test_mode == 'false')
        env:
          GEMINI_API_KEY: ${{{{ secrets.GEMINI_API_KEY }}}}
          GMAIL_USER: ${{{{ secrets.GMAIL_USER }}}}
          GMAIL_APP_PASSWORD: ${{{{ secrets.GMAIL_APP_PASSWORD }}}}
          X_COOKIES_JSON: ${{{{ secrets.X_COOKIES_JSON }}}}
          GITHUB_TOKEN: ${{{{ secrets.GITHUB_TOKEN }}}}
        run: python main.py

      - name: 週次レポート実行
        if: github.event_name == 'workflow_dispatch' && github.event.inputs.report_type == 'weekly' && github.event.inputs.test_mode == 'false'
        env:
          GEMINI_API_KEY: ${{{{ secrets.GEMINI_API_KEY }}}}
          GMAIL_USER: ${{{{ secrets.GMAIL_USER }}}}
          GMAIL_APP_PASSWORD: ${{{{ secrets.GMAIL_APP_PASSWORD }}}}
          X_COOKIES_JSON: ${{{{ secrets.X_COOKIES_JSON }}}}
          GITHUB_TOKEN: ${{{{ secrets.GITHUB_TOKEN }}}}
        run: python main.py --weekly

      - name: テスト実行（メール送信なし）
        if: github.event_name == 'workflow_dispatch' && github.event.inputs.test_mode == 'true'
        env:
          GEMINI_API_KEY: ${{{{ secrets.GEMINI_API_KEY }}}}
          GMAIL_USER: ${{{{ secrets.GMAIL_USER }}}}
          GMAIL_APP_PASSWORD: ${{{{ secrets.GMAIL_APP_PASSWORD }}}}
          X_COOKIES_JSON: ${{{{ secrets.X_COOKIES_JSON }}}}
          GITHUB_TOKEN: ${{{{ secrets.GITHUB_TOKEN }}}}
        run: |
          if [ "${{{{ github.event.inputs.report_type }}}}" = "weekly" ]; then
            python main.py --weekly --test
          else
            python main.py --test
          fi

      - name: ログをアーティファクトとして保存
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: logs-${{{{ github.run_number }}}}
          path: logs/
          retention-days: 7
"""
    try:
        os.makedirs(os.path.dirname(WORKFLOW_FILE), exist_ok=True)
        with open(WORKFLOW_FILE, "w", encoding="utf-8") as f:
            f.write(yml)
        return jsonify({"success": True, "message": "monitor.yml を保存しました。GitHub Desktop でプッシュしてください。"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route("/settings")
def settings_page():
    settings = load_settings()
    return render_template_string('{% extends "settings" %}', settings=settings)


@app.route("/settings/save", methods=["POST"])
def save_settings_page():
    data = {
        "x_cookies": {
            "auth_token": request.form.get("auth_token", "").strip(),
            "ct0": request.form.get("ct0", "").strip(),
            "twid": request.form.get("twid", "").strip(),
        },
        "gemini_api_key": request.form.get("gemini_api_key", "").strip(),
        "gemini_model": request.form.get("gemini_model", "gemini-2.5-flash").strip(),
        "gmail_user": request.form.get("gmail_user", "").strip(),
        "gmail_app_password": request.form.get("gmail_app_password", "").strip(),
        "max_tweets": int(request.form.get("max_tweets", 100)),
        "search_interval": int(request.form.get("search_interval", 5)),
    }
    save_settings(data)
    flash("✅ 設定を保存しました", "success")
    return redirect(url_for("settings_page"))


@app.route("/test_connection", methods=["POST"])
def test_connection():
    results = []
    s = load_settings()

    # X Cookie テスト（Playwrightで確認）
    if not s["x_cookies"].get("auth_token"):
        results.append("❌ X Cookie: auth_token が未設定")
    else:
        results.append("✅ X Cookie: auth_token が設定されています（Playwright方式のため実接続テストはスキップ）")

    # Gemini テスト
    if not s["gemini_api_key"]:
        results.append("❌ Gemini APIキーが未設定")
    else:
        try:
            from google import genai
            client = genai.Client(api_key=s["gemini_api_key"])
            response = client.models.generate_content(
                model=s.get("gemini_model", "gemini-2.5-flash"),
                contents="テスト。「OK」とだけ返してください。"
            )
            results.append(f"✅ Gemini API OK: {response.text.strip()[:30]}")
        except Exception as e:
            results.append(f"❌ Gemini APIエラー: {e}")

    # Gmail テスト
    if not s["gmail_user"] or not s["gmail_app_password"]:
        results.append("❌ Gmail設定が未入力")
    else:
        try:
            import smtplib
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(s["gmail_user"], s["gmail_app_password"])
            results.append("✅ Gmail SMTP接続OK")
        except Exception as e:
            results.append(f"❌ Gmail接続エラー: {e}")

    return jsonify({"results": results})


@app.route("/reports")
def reports_page():
    reports = get_recent_reports()
    return render_template_string('{% extends "reports" %}', reports=reports)


@app.route("/reports/<filename>")
def view_report(filename):
    filepath = os.path.join(REPORTS_DIR, filename)
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    return "レポートが見つかりません", 404


@app.route("/run", methods=["POST"])
def run_manual():
    """旧ルート（互換性のため残す）"""
    return redirect(url_for("index"))


@app.route("/run_async", methods=["POST"])
def run_async():
    """非同期実行 - 完了を待ってから結果を返す"""
    mode = request.form.get("mode", "test")
    try:
        import subprocess
        cmd = [sys.executable, os.path.join(SCRIPT_DIR, "main.py")]
        if mode == "test":
            cmd.append("--test")
        elif mode == "weekly":
            cmd.append("--weekly")

        result = subprocess.run(
            cmd, cwd=SCRIPT_DIR, capture_output=True, text=True, timeout=3600
        )

        # 最新のレポートファイルを取得
        report_file = None
        if os.path.exists(REPORTS_DIR):
            files = sorted(
                [f for f in os.listdir(REPORTS_DIR) if f.endswith(".html")],
                reverse=True
            )
            if files:
                report_file = files[0]

        if result.returncode == 0:
            return jsonify({
                "success": True,
                "message": "処理が正常に完了しました。",
                "report": report_file,
            })
        else:
            return jsonify({
                "success": False,
                "message": f"処理中にエラーが発生しました:\n{result.stderr[-500:] if result.stderr else '詳細不明'}",
                "report": report_file,
            })

    except subprocess.TimeoutExpired:
        return jsonify({
            "success": False,
            "message": "タイムアウト（60分以上かかりました）。対象人物が多すぎる可能性があります。",
            "report": None,
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"実行エラー: {str(e)}",
            "report": None,
        })


if __name__ == "__main__":
    print("=" * 50)
    print("X有名人モニタリング - Web管理画面")
    print("ブラウザで http://localhost:5001 にアクセス")
    print("終了: Ctrl+C")
    print("=" * 50)
    app.run(host="127.0.0.1", port=5001, debug=True)
