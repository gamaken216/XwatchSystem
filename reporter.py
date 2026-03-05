"""
HTMLレポート生成モジュール
==========================
分析結果を見やすいHTMLレポートに変換する。
"""
import os
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(SCRIPT_DIR, "reports")


def generate_html_report(analyzed_data, report_type="daily"):
    """
    分析データからHTMLレポートを生成する。

    Args:
        analyzed_data: analyzer.analyze_all() の戻り値
        report_type: "daily" or "weekly"

    Returns:
        str: 生成したHTMLファイルのパス
    """
    os.makedirs(REPORTS_DIR, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    title = f"X モニタリングレポート（{'日次' if report_type == 'daily' else '週次'}）"

    # --- HTMLヘッダー ---
    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} - {today}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Hiragino Sans', 'Yu Gothic', sans-serif; background: #f5f7fa; color: #2c3e50; }}
.container {{ max-width: 900px; margin: 0 auto; padding: 20px; }}
.header {{ background: linear-gradient(135deg, #1E2761, #4A6FA5); color: white; padding: 30px; border-radius: 12px; margin-bottom: 24px; }}
.header h1 {{ font-size: 24px; margin-bottom: 8px; }}
.header .date {{ font-size: 14px; opacity: 0.8; }}
.summary-card {{ background: white; border-radius: 12px; padding: 24px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
.summary-card h2 {{ font-size: 18px; color: #1E2761; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #E8C547; }}
.person-section {{ background: white; border-radius: 12px; padding: 24px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
.person-section h3 {{ font-size: 20px; color: #1E2761; margin-bottom: 4px; }}
.person-category {{ display: inline-block; background: #EBF5FB; color: #4A6FA5; padding: 2px 10px; border-radius: 12px; font-size: 12px; margin-bottom: 16px; }}
.stats {{ display: flex; gap: 12px; margin-bottom: 16px; }}
.stat-box {{ flex: 1; text-align: center; padding: 12px; border-radius: 8px; }}
.stat-box.positive {{ background: #E8F8F5; color: #27AE60; }}
.stat-box.negative {{ background: #FDEDEC; color: #E74C3C; }}
.stat-box.neutral {{ background: #F4F6F7; color: #6B7280; }}
.stat-box .num {{ font-size: 28px; font-weight: bold; }}
.stat-box .label {{ font-size: 12px; }}
.summary-text {{ background: #f8f9fa; padding: 16px; border-radius: 8px; margin-bottom: 16px; line-height: 1.7; }}
.alert {{ background: #FEF3E2; border-left: 4px solid #F39C12; padding: 12px 16px; border-radius: 0 8px 8px 0; margin-bottom: 16px; }}
.alert-danger {{ background: #FDEDEC; border-left-color: #E74C3C; }}
.tweet-card {{ border: 1px solid #e5e7eb; border-radius: 8px; padding: 14px; margin-bottom: 10px; }}
.tweet-card .meta {{ font-size: 12px; color: #6B7280; margin-bottom: 6px; }}
.tweet-card .text {{ line-height: 1.6; margin-bottom: 8px; }}
.tweet-card .engagement {{ font-size: 12px; color: #6B7280; }}
.tweet-card .reason {{ font-size: 12px; color: #4A6FA5; font-style: italic; margin-top: 6px; }}
.chart-container {{ max-width: 300px; margin: 16px auto; }}
.category-list {{ list-style: none; }}
.category-list li {{ padding: 6px 0; border-bottom: 1px solid #f0f0f0; display: flex; justify-content: space-between; }}
.category-list li:last-child {{ border-bottom: none; }}
.footer {{ text-align: center; color: #999; font-size: 12px; padding: 20px; }}
.all-tweets {{ margin-top: 20px; }}
.all-tweets summary {{ cursor: pointer; padding: 12px 16px; background: #1E2761; color: white; border-radius: 8px; font-size: 14px; font-weight: bold; }}
.all-tweets summary:hover {{ background: #2a3578; }}
.all-tweets[open] summary {{ border-radius: 8px 8px 0 0; }}
.all-tweets .tweets-list {{ border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 8px 8px; max-height: 600px; overflow-y: auto; }}
.all-tweets .tweet-item {{ padding: 12px 16px; border-bottom: 1px solid #f0f0f0; }}
.all-tweets .tweet-item:last-child {{ border-bottom: none; }}
.all-tweets .tweet-item .tw-meta {{ font-size: 12px; color: #6B7280; margin-bottom: 4px; }}
.all-tweets .tweet-item .tw-text {{ font-size: 14px; line-height: 1.6; margin-bottom: 6px; }}
.all-tweets .tweet-item .tw-stats {{ font-size: 12px; color: #6B7280; }}
.all-tweets .tweet-item .tw-link {{ font-size: 12px; }}
.all-tweets .tweet-item:nth-child(even) {{ background: #fafbfc; }}
</style>
</head>
<body>
<div class="container">
<div class="header">
    <h1>{title}</h1>
    <div class="date">{datetime.now().strftime("%Y年%m月%d日 %H:%M")} 生成</div>
</div>
"""

    # --- エグゼクティブサマリー ---
    total_tweets = sum(len(d["tweets"]) for d in analyzed_data.values())
    total_positive = sum(d["analysis"]["sentiment"]["positive"] for d in analyzed_data.values())
    total_negative = sum(d["analysis"]["sentiment"]["negative"] for d in analyzed_data.values())
    total_neutral = sum(d["analysis"]["sentiment"]["neutral"] for d in analyzed_data.values())
    alerts = [d for d in analyzed_data.values() if d["analysis"].get("alert")]

    html += f"""
<div class="summary-card">
    <h2>エグゼクティブサマリー</h2>
    <div class="stats">
        <div class="stat-box" style="background:#EBF5FB; color:#1E2761;">
            <div class="num">{len(analyzed_data)}</div>
            <div class="label">対象人物</div>
        </div>
        <div class="stat-box" style="background:#EBF5FB; color:#1E2761;">
            <div class="num">{total_tweets}</div>
            <div class="label">総ツイート数</div>
        </div>
        <div class="stat-box positive">
            <div class="num">{total_positive}</div>
            <div class="label">ポジティブ</div>
        </div>
        <div class="stat-box negative">
            <div class="num">{total_negative}</div>
            <div class="label">ネガティブ</div>
        </div>
        <div class="stat-box neutral">
            <div class="num">{total_neutral}</div>
            <div class="label">ニュートラル</div>
        </div>
    </div>
"""
    if alerts:
        for a in alerts:
            html += f'    <div class="alert alert-danger">⚠ {a["target"]["name"]}: {a["analysis"]["alert"]}</div>\n'

    html += "</div>\n"

    # --- 人物別詳細 ---
    for tid, data in analyzed_data.items():
        target = data["target"]
        analysis = data["analysis"]
        tweets = data["tweets"]
        sent = analysis["sentiment"]

        html += f"""
<div class="person-section">
    <h3>{target["name"]}</h3>
    <span class="person-category">{target.get("category", "")}</span>

    <div class="stats">
        <div class="stat-box positive">
            <div class="num">{sent["positive"]}</div>
            <div class="label">ポジティブ</div>
        </div>
        <div class="stat-box negative">
            <div class="num">{sent["negative"]}</div>
            <div class="label">ネガティブ</div>
        </div>
        <div class="stat-box neutral">
            <div class="num">{sent["neutral"]}</div>
            <div class="label">ニュートラル</div>
        </div>
    </div>

    <div class="summary-text">{analysis["summary"]}</div>
"""
        # アラート
        if analysis.get("alert"):
            html += f'    <div class="alert alert-danger">⚠ {analysis["alert"]}</div>\n'

        # カテゴリ
        if analysis.get("categories"):
            html += '    <h4 style="margin-bottom:8px;">カテゴリ別</h4>\n'
            html += '    <ul class="category-list">\n'
            for cat, count in sorted(analysis["categories"].items(), key=lambda x: -x[1]):
                html += f'        <li><span>{cat}</span><strong>{count}件</strong></li>\n'
            html += '    </ul>\n'

        # 注目ツイート
        top_tweets = analysis.get("top_tweets", [])
        if top_tweets and tweets:
            html += '    <h4 style="margin:16px 0 8px;">注目ツイート</h4>\n'
            for tt in top_tweets[:5]:
                idx = tt.get("index", 1) - 1
                if 0 <= idx < len(tweets):
                    tw = tweets[idx]
                    html += f"""    <div class="tweet-card">
        <div class="meta">@{tw["user"]} - {tw["created_at"]}</div>
        <div class="text">{tw["text"]}</div>
        <div class="engagement">❤ {tw["favorite_count"]}  🔄 {tw["retweet_count"]}</div>
        <div class="reason">📌 {tt.get("reason", "")}</div>
    </div>\n"""

        html += "</div>\n"""

        # 全ツイート一覧（折りたたみ式）
        if tweets:
            html += f"""    <details class="all-tweets">
        <summary>📋 全ツイート一覧を表示（{len(tweets)}件）</summary>
        <div class="tweets-list">\n"""
            for i, tw in enumerate(tweets, 1):
                tweet_url = tw.get("url", f"https://x.com/{tw['user']}/status/{tw['id']}")
                html += f"""            <div class="tweet-item">
                <div class="tw-meta">#{i} @{tw["user"]}（{tw.get("user_name", "")}）- {tw["created_at"]}</div>
                <div class="tw-text">{tw["text"]}</div>
                <div class="tw-stats">❤ {tw["favorite_count"]}  🔄 {tw["retweet_count"]}  💬 {tw.get("quote_count", 0)}
                    <span class="tw-link"> | <a href="{tweet_url}" target="_blank" style="color:#4A6FA5;">元のツイートを見る</a></span>
                </div>
            </div>\n"""
            html += """        </div>
    </details>\n"""

        html += "</div>\n"

    # --- フッター ---
    html += f"""
<div class="footer">
    X有名人モニタリングシステム - {datetime.now().strftime("%Y年%m月%d日")} 自動生成
</div>
</div>
</body>
</html>"""

    # ファイル保存
    filename = f"report_{report_type}_{today}.html"
    filepath = os.path.join(REPORTS_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"  レポート生成: {filepath}")
    return filepath


# テスト用
if __name__ == "__main__":
    print("reporter.py - テストにはmain.pyを実行してください")
