"""
HTMLレポート生成モジュール
==========================
2種類のレポートを生成する：
1. メール用HTML    : 全体要約 + 注目ツイート + ウェブへの誘導ボタン
2. ウェブ用HTML    : 全ツイート一覧（GitHub Pages公開用）
"""
import os
import json
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.join(SCRIPT_DIR, "docs")
REPORTS_DIR = os.path.join(DOCS_DIR, "reports")

GITHUB_PAGES_URL = "https://gamaken216.github.io/XwatchSystem"


def _sentiment_bar(positive, negative, neutral):
    total = positive + negative + neutral
    if total == 0:
        return ""
    p = int(positive / total * 100)
    n = int(negative / total * 100)
    neu = 100 - p - n
    return f"""<div style="display:flex;border-radius:6px;overflow:hidden;height:10px;margin:8px 0 4px;">
    <div style="width:{p}%;background:#27AE60;"></div>
    <div style="width:{neu}%;background:#BDC3C7;"></div>
    <div style="width:{n}%;background:#E74C3C;"></div>
</div>
<div style="font-size:11px;color:#666;display:flex;gap:12px;margin-bottom:12px;">
    <span>🟢 ポジティブ {positive}件</span>
    <span>⚪ ニュートラル {neutral}件</span>
    <span>🔴 ネガティブ {negative}件</span>
</div>"""


def generate_web_report(analyzed_data, report_type="daily"):
    """
    ウェブ用の全ツイート一覧HTMLを生成してdocs/reports/に保存する。
    GitHub Pagesで公開される。
    """
    os.makedirs(REPORTS_DIR, exist_ok=True)
    os.makedirs(DOCS_DIR, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    now_str = datetime.now().strftime("%Y年%m月%d日 %H:%M")
    type_label = "日次" if report_type == "daily" else "週次"
    title = f"X モニタリングレポート（{type_label}）"

    total_tweets = sum(len(d["tweets"]) for d in analyzed_data.values())
    total_positive = sum(d["analysis"]["sentiment"]["positive"] for d in analyzed_data.values())
    total_negative = sum(d["analysis"]["sentiment"]["negative"] for d in analyzed_data.values())
    total_neutral = sum(d["analysis"]["sentiment"]["neutral"] for d in analyzed_data.values())

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} - {today}</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Hiragino Sans','Yu Gothic',sans-serif; background:#eef4fb; color:#1a2744; }}
.container {{ max-width:960px; margin:0 auto; padding:20px; }}
.header {{ background:linear-gradient(135deg,#1a6fd4,#0ea5e9); color:white; padding:28px; border-radius:16px; margin-bottom:24px; box-shadow:0 4px 20px rgba(26,111,212,0.25); }}
.header h1 {{ font-size:20px; margin-bottom:6px; }}
.header .meta {{ font-size:12px; opacity:0.8; }}
.back {{ display:inline-block; margin-bottom:16px; color:#1a6fd4; text-decoration:none; font-size:13px; font-weight:600; background:white; padding:6px 14px; border-radius:20px; border:1px solid #c5d8f0; }}
.back:hover {{ background:#e8f1fd; }}
.card {{ background:white; border-radius:12px; padding:24px; margin-bottom:20px; box-shadow:0 2px 8px rgba(26,111,212,0.06); border:1px solid #c5d8f0; }}
.card-title {{ font-size:12px; font-weight:700; color:#1a6fd4; text-transform:uppercase; letter-spacing:1px; margin-bottom:16px; padding-bottom:8px; border-bottom:2px solid #0ea5e9; }}
.stats {{ display:flex; gap:12px; margin-bottom:16px; flex-wrap:wrap; }}
.stat {{ flex:1; min-width:80px; text-align:center; padding:12px; border-radius:8px; }}
.stat .num {{ font-size:26px; font-weight:700; }}
.stat .lbl {{ font-size:11px; margin-top:2px; }}
.person-name {{ font-size:18px; font-weight:700; margin-bottom:4px; }}
.category-badge {{ display:inline-block; background:#e8f1fd; color:#1a6fd4; font-size:11px; font-weight:600; padding:2px 8px; border-radius:12px; margin-bottom:12px; }}
.summary-text {{ background:#f0f6ff; padding:14px; border-radius:8px; line-height:1.7; font-size:14px; margin-bottom:16px; }}
.alert-box {{ background:#fff5f5; border-left:4px solid #E74C3C; padding:12px 16px; border-radius:0 8px 8px 0; margin-bottom:16px; font-size:13px; }}
.section-label {{ font-size:13px; font-weight:700; color:#1a2744; margin:16px 0 10px; }}
.tweet-item {{ border:1px solid #e5e7eb; border-radius:8px; padding:14px; margin-bottom:10px; background:white; }}
.tweet-item:nth-child(even) {{ background:#fafbfc; }}
.tweet-meta {{ font-size:12px; color:#6B7280; margin-bottom:6px; }}
.tweet-text {{ line-height:1.6; font-size:14px; margin-bottom:8px; }}
.tweet-stats {{ font-size:12px; color:#6B7280; }}
.tweet-link {{ color:#1a6fd4; text-decoration:none; }}
.tweet-link:hover {{ text-decoration:underline; }}
.filter-bar {{ display:flex; gap:8px; margin-bottom:16px; flex-wrap:wrap; align-items:center; }}
.filter-btn {{ padding:6px 14px; border-radius:20px; border:1.5px solid #c5d8f0; background:white; color:#5a7499; font-size:12px; font-weight:600; cursor:pointer; transition:all 0.2s; }}
.filter-btn:hover, .filter-btn.active {{ background:#1a6fd4; color:white; border-color:#1a6fd4; }}
.count-badge {{ font-size:11px; background:#e8f1fd; color:#1a6fd4; padding:2px 6px; border-radius:10px; margin-left:4px; }}
.footer {{ text-align:center; color:#999; font-size:12px; padding:24px; }}
</style>
</head>
<body>
<div class="container">
    <a href="../index.html" class="back">← レポート一覧に戻る</a>
    <div class="header">
        <h1>{title}</h1>
        <div class="meta">{now_str} 生成 ／ 総ツイート {total_tweets}件</div>
    </div>
"""

    # 全体サマリー
    html += f"""    <div class="card">
        <div class="card-title">エグゼクティブサマリー</div>
        <div class="stats">
            <div class="stat" style="background:#e8f1fd;color:#1a6fd4;">
                <div class="num">{len(analyzed_data)}</div><div class="lbl">対象人物</div>
            </div>
            <div class="stat" style="background:#e8f1fd;color:#1a6fd4;">
                <div class="num">{total_tweets}</div><div class="lbl">総ツイート数</div>
            </div>
            <div class="stat" style="background:#e8f8f5;color:#27AE60;">
                <div class="num">{total_positive}</div><div class="lbl">ポジティブ</div>
            </div>
            <div class="stat" style="background:#f4f6f7;color:#6B7280;">
                <div class="num">{total_neutral}</div><div class="lbl">ニュートラル</div>
            </div>
            <div class="stat" style="background:#fdedec;color:#E74C3C;">
                <div class="num">{total_negative}</div><div class="lbl">ネガティブ</div>
            </div>
        </div>
    </div>
"""

    # 人物別詳細
    for tid, data in analyzed_data.items():
        target = data["target"]
        analysis = data["analysis"]
        tweets = data["tweets"]
        sent = analysis["sentiment"]

        html += f"""    <div class="card">
        <div class="person-name">{target["name"]}</div>
        <span class="category-badge">{target.get("category","")}</span>
        {_sentiment_bar(sent["positive"], sent["negative"], sent["neutral"])}
        <div class="summary-text">{analysis["summary"]}</div>
"""
        if analysis.get("alert"):
            html += f'        <div class="alert-box">⚠️ {analysis["alert"]}</div>\n'

        # 全ツイート一覧
        if tweets:
            html += f"""        <div class="section-label">全ツイート一覧（{len(tweets)}件）</div>
        <div class="filter-bar">
            <button class="filter-btn active" onclick="filterTweets('{tid}','all',this)">すべて <span class="count-badge">{len(tweets)}</span></button>
            <button class="filter-btn" onclick="filterTweets('{tid}','positive',this)">🟢 ポジティブ <span class="count-badge">{sent["positive"]}</span></button>
            <button class="filter-btn" onclick="filterTweets('{tid}','neutral',this)">⚪ ニュートラル <span class="count-badge">{sent["neutral"]}</span></button>
            <button class="filter-btn" onclick="filterTweets('{tid}','negative',this)">🔴 ネガティブ <span class="count-badge">{sent["negative"]}</span></button>
        </div>
        <div id="tweets-{tid}">
"""
            # ツイートの感情をtweetDetailsから取得
            tweet_details = {td["index"]: td.get("sentiment","neutral") for td in analysis.get("tweet_details",[])}
            for i, tw in enumerate(tweets, 1):
                sentiment = tweet_details.get(i, "neutral")
                html += f"""            <div class="tweet-item" data-sentiment="{sentiment}">
                <div class="tweet-meta">@{tw["user"]}（{tw.get("user_name","")}）- {tw["created_at"]}</div>
                <div class="tweet-text">{tw["text"]}</div>
                <div class="tweet-stats">❤ {tw["favorite_count"]}　🔄 {tw["retweet_count"]}　
                    <a href="{tw.get("url","")}" target="_blank" class="tweet-link">元のツイートを見る →</a>
                </div>
            </div>
"""
            html += "        </div>\n    </div>\n"

    html += """
<div class="footer">X有名人モニタリングシステム - 自動生成</div>
</div>

<script>
function filterTweets(tid, sentiment, btn) {
    const container = document.getElementById('tweets-' + tid);
    const items = container.querySelectorAll('.tweet-item');
    items.forEach(item => {
        item.style.display = (sentiment === 'all' || item.dataset.sentiment === sentiment) ? '' : 'none';
    });
    btn.closest('.filter-bar').querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
}
</script>
</body>
</html>"""

    filename = f"report_{report_type}_{today}.html"
    filepath = os.path.join(REPORTS_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  ウェブレポート生成: {filepath}")

    # index.htmlを更新
    _update_index(report_type, today, analyzed_data, filename)

    return filepath


def _update_index(report_type, today, analyzed_data, filename):
    """docs/index.html のレポート一覧を更新する"""
    index_path = os.path.join(DOCS_DIR, "index.html")
    type_label = "日次" if report_type == "daily" else "週次"
    total_tweets = sum(len(d["tweets"]) for d in analyzed_data.values())
    names = "、".join(d["target"]["name"] for d in analyzed_data.values())
    new_entry = f'<li data-date="{today}"><a href="reports/{filename}">【{type_label}】{today} - {names}（{total_tweets}件）</a></li>\n'

    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            content = f.read()
        content = content.replace("<!-- REPORTS -->", f"<!-- REPORTS -->\n        {new_entry}")
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(content)
    else:
        _create_index(new_entry)


def _create_index(first_entry=""):
    """docs/index.html を新規作成する"""
    os.makedirs(DOCS_DIR, exist_ok=True)
    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>X モニタリング レポート一覧</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Hiragino Sans','Yu Gothic',sans-serif; background:#eef4fb; color:#1a2744; }}
.container {{ max-width:800px; margin:0 auto; padding:24px; }}
.header {{ background:linear-gradient(135deg,#1a6fd4,#0ea5e9); color:white; padding:28px; border-radius:16px; margin-bottom:24px; box-shadow:0 4px 20px rgba(26,111,212,0.25); }}
.header h1 {{ font-size:22px; margin-bottom:6px; }}
.header p {{ font-size:13px; opacity:0.8; }}
.card {{ background:white; border-radius:12px; padding:24px; box-shadow:0 2px 8px rgba(26,111,212,0.06); border:1px solid #c5d8f0; }}
.card-title {{ font-size:12px; font-weight:700; color:#1a6fd4; text-transform:uppercase; letter-spacing:1px; margin-bottom:16px; padding-bottom:8px; border-bottom:2px solid #0ea5e9; }}
ul {{ list-style:none; }}
li {{ padding:12px 0; border-bottom:1px solid #f0f4f8; }}
li:last-child {{ border-bottom:none; }}
a {{ color:#1a6fd4; text-decoration:none; font-size:14px; font-weight:500; }}
a:hover {{ text-decoration:underline; }}
.footer {{ text-align:center; color:#999; font-size:12px; padding:24px; }}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>👁 X モニタリング レポート一覧</h1>
        <p>有名人に関するXの投稿を毎日自動収集・分析しています</p>
    </div>
    <div class="card">
        <div class="card-title">レポート履歴</div>
        <ul>
        <!-- REPORTS -->
        {first_entry}
        </ul>
    </div>
    <div class="footer">X有名人モニタリングシステム - 自動生成</div>
</div>
</body>
</html>"""
    index_path = os.path.join(DOCS_DIR, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  index.html 作成: {index_path}")


def generate_email_html(analyzed_data, report_type="daily", web_url=None):
    """
    メール用HTMLを生成する。
    全体要約 + 注目ツイート + ウェブ版への誘導ボタン付き。
    """
    today = datetime.now().strftime("%Y-%m-%d")
    now_str = datetime.now().strftime("%Y年%m月%d日 %H:%M")
    type_label = "日次" if report_type == "daily" else "週次"
    title = f"X モニタリングレポート（{type_label}）"

    total_tweets = sum(len(d["tweets"]) for d in analyzed_data.values())
    total_positive = sum(d["analysis"]["sentiment"]["positive"] for d in analyzed_data.values())
    total_negative = sum(d["analysis"]["sentiment"]["negative"] for d in analyzed_data.values())
    total_neutral = sum(d["analysis"]["sentiment"]["neutral"] for d in analyzed_data.values())
    alerts = [d for d in analyzed_data.values() if d["analysis"].get("alert")]

    web_link = web_url or f"{GITHUB_PAGES_URL}/reports/report_{report_type}_{today}.html"

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
</head>
<body style="margin:0;padding:0;background:#eef4fb;font-family:'Hiragino Sans','Yu Gothic',sans-serif;">
<div style="max-width:700px;margin:0 auto;padding:20px;">

    <!-- ヘッダー -->
    <div style="background:linear-gradient(135deg,#1a6fd4,#0ea5e9);color:white;padding:28px;border-radius:16px;margin-bottom:20px;">
        <h1 style="font-size:20px;margin:0 0 6px;">{title}</h1>
        <p style="font-size:12px;margin:0;opacity:0.8;">{now_str} 生成 ／ 総ツイート {total_tweets}件</p>
    </div>
"""

    # アラートがあれば最初に表示
    for a in alerts:
        html += f"""    <div style="background:#fff5f5;border-left:4px solid #E74C3C;padding:12px 16px;border-radius:0 8px 8px 0;margin-bottom:16px;font-size:13px;">
        ⚠️ <strong>{a["target"]["name"]}</strong>: {a["analysis"]["alert"]}
    </div>
"""

    # 全体サマリー
    html += f"""    <div style="background:white;border-radius:12px;padding:20px;margin-bottom:16px;border:1px solid #c5d8f0;">
        <div style="font-size:11px;font-weight:700;color:#1a6fd4;text-transform:uppercase;letter-spacing:1px;margin-bottom:14px;padding-bottom:8px;border-bottom:2px solid #0ea5e9;">エグゼクティブサマリー</div>
        <table width="100%" cellpadding="0" cellspacing="0"><tr>
            <td align="center" style="background:#e8f1fd;border-radius:8px;padding:10px;color:#1a6fd4;">
                <div style="font-size:24px;font-weight:700;">{len(analyzed_data)}</div><div style="font-size:11px;">対象人物</div>
            </td>
            <td width="8"></td>
            <td align="center" style="background:#e8f1fd;border-radius:8px;padding:10px;color:#1a6fd4;">
                <div style="font-size:24px;font-weight:700;">{total_tweets}</div><div style="font-size:11px;">総ツイート数</div>
            </td>
            <td width="8"></td>
            <td align="center" style="background:#e8f8f5;border-radius:8px;padding:10px;color:#27AE60;">
                <div style="font-size:24px;font-weight:700;">{total_positive}</div><div style="font-size:11px;">ポジティブ</div>
            </td>
            <td width="8"></td>
            <td align="center" style="background:#f4f6f7;border-radius:8px;padding:10px;color:#6B7280;">
                <div style="font-size:24px;font-weight:700;">{total_neutral}</div><div style="font-size:11px;">ニュートラル</div>
            </td>
            <td width="8"></td>
            <td align="center" style="background:#fdedec;border-radius:8px;padding:10px;color:#E74C3C;">
                <div style="font-size:24px;font-weight:700;">{total_negative}</div><div style="font-size:11px;">ネガティブ</div>
            </td>
        </tr></table>
    </div>
"""

    # 人物別詳細
    for tid, data in analyzed_data.items():
        target = data["target"]
        analysis = data["analysis"]
        tweets = data["tweets"]
        sent = analysis["sentiment"]
        top_tweets = analysis.get("top_tweets", [])

        html += f"""    <div style="background:white;border-radius:12px;padding:20px;margin-bottom:16px;border:1px solid #c5d8f0;">
        <h2 style="font-size:18px;margin:0 0 4px;color:#1a2744;">{target["name"]}</h2>
        <span style="display:inline-block;background:#e8f1fd;color:#1a6fd4;font-size:11px;font-weight:600;padding:2px 8px;border-radius:12px;margin-bottom:12px;">{target.get("category","")}</span>

        <!-- センチメントバー -->
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:8px;"><tr>
"""
        total = sent["positive"] + sent["negative"] + sent["neutral"]
        if total > 0:
            p = int(sent["positive"] / total * 100)
            n = int(sent["negative"] / total * 100)
            neu = 100 - p - n
            html += f"""            <td width="{p}%" style="background:#27AE60;height:10px;border-radius:6px 0 0 6px;"></td>
            <td width="{neu}%" style="background:#BDC3C7;height:10px;"></td>
            <td width="{n}%" style="background:#E74C3C;height:10px;border-radius:0 6px 6px 0;"></td>
"""
        html += f"""        </tr></table>
        <p style="font-size:11px;color:#666;margin-bottom:12px;">🟢 {sent["positive"]}件　⚪ {sent["neutral"]}件　🔴 {sent["negative"]}件</p>

        <!-- 全体要約 -->
        <div style="background:#f0f6ff;padding:14px;border-radius:8px;line-height:1.7;font-size:14px;margin-bottom:16px;">{analysis["summary"]}</div>
"""
        if analysis.get("alert"):
            html += f'        <div style="background:#fff5f5;border-left:4px solid #E74C3C;padding:10px 14px;border-radius:0 8px 8px 0;margin-bottom:16px;font-size:13px;">⚠️ {analysis["alert"]}</div>\n'

        # 注目ツイート
        if top_tweets and tweets:
            html += '        <p style="font-size:13px;font-weight:700;color:#1a2744;margin-bottom:10px;">📌 注目ツイート</p>\n'
            for tt in top_tweets[:5]:
                idx = tt.get("index", 1) - 1
                if 0 <= idx < len(tweets):
                    tw = tweets[idx]
                    sentiment_color = {"positive": "#27AE60", "negative": "#E74C3C", "neutral": "#6B7280"}.get(tt.get("sentiment","neutral"), "#6B7280")
                    html += f"""        <div style="border:1px solid #e5e7eb;border-radius:8px;padding:12px;margin-bottom:8px;">
            <div style="font-size:12px;color:#6B7280;margin-bottom:4px;">@{tw["user"]}　{tw["created_at"]}</div>
            <div style="font-size:14px;line-height:1.6;margin-bottom:6px;">{tw["text"]}</div>
            <div style="font-size:12px;color:#6B7280;">❤ {tw["favorite_count"]}　🔄 {tw["retweet_count"]}</div>
            <div style="font-size:12px;color:{sentiment_color};margin-top:4px;font-style:italic;">📌 {tt.get("reason","")}</div>
        </div>
"""

        html += "    </div>\n"

    # ウェブ版へのリンクボタン
    html += f"""
    <div style="text-align:center;margin:24px 0;">
        <p style="font-size:13px;color:#5a7499;margin-bottom:12px;">全ツイート一覧・感情別フィルターはウェブ版でご覧いただけます</p>
        <a href="{web_link}" style="display:inline-block;background:linear-gradient(135deg,#1a6fd4,#0ea5e9);color:white;padding:14px 32px;border-radius:10px;text-decoration:none;font-size:14px;font-weight:700;box-shadow:0 4px 12px rgba(26,111,212,0.3);">
            🌐 全ツイートをウェブで見る →
        </a>
        <br><br>
        <a href="{GITHUB_PAGES_URL}" style="font-size:12px;color:#1a6fd4;text-decoration:none;">過去のレポート一覧はこちら</a>
    </div>

    <div style="text-align:center;color:#999;font-size:11px;padding:16px;">
        X有名人モニタリングシステム - 自動生成
    </div>
</div>
</body>
</html>"""

    return html


def generate_html_report(analyzed_data, report_type="daily"):
    """後方互換性のため残す。ウェブ用レポートを生成してパスを返す。"""
    return generate_web_report(analyzed_data, report_type)
