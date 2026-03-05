"""
メール配信モジュール
====================
Gmail SMTPでHTMLレポートをメール送信する。
Dropbox共有リンクをフッターに自動挿入。
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime


# Dropbox共有リンク（reports フォルダの共有リンクを設定してください）
DROPBOX_SHARE_LINK = "https://www.dropbox.com/scl/fo/adcm5oha5rb6ggix4k5vm/AHimbPkUKUwRQsNRUAdpFX8?rlkey=dqya7ix93d8tj26v6ap9ha4zj&dl=0"


def send_report(gmail_user, gmail_password, recipients, html_filepath, report_type="daily", dropbox_link=None):
    """
    HTMLレポートをメールで送信する。

    Args:
        gmail_user: Gmailアドレス
        gmail_password: アプリパスワード
        recipients: 送信先リスト
        html_filepath: HTMLレポートファイルのパス
        report_type: "daily" or "weekly"
        dropbox_link: Dropbox共有リンク（Noneの場合はDROPBOX_SHARE_LINKを使用）
    """
    today = datetime.now().strftime("%Y年%m月%d日")
    type_label = "日次" if report_type == "daily" else "週次"
    subject = f"【X モニタリング】{type_label}レポート - {today}"

    share_link = dropbox_link or DROPBOX_SHARE_LINK

    with open(html_filepath, "r", encoding="utf-8") as f:
        html_content = f.read()

    # HTMLレポートにDropboxリンク付きフッターを追加
    if share_link:
        footer_html = f"""
<div style="margin-top:30px; padding:20px; background:#f8f9fa; border-top:2px solid #E8C547; text-align:center; font-family:'Hiragino Sans','Yu Gothic',sans-serif;">
    <p style="font-size:14px; color:#1E2761; margin-bottom:8px;">
        📂 過去のレポートはいつでもこちらからご覧いただけます
    </p>
    <a href="{share_link}" style="display:inline-block; padding:10px 24px; background:#1E2761; color:white; text-decoration:none; border-radius:6px; font-size:14px; font-weight:bold;">
        レポート一覧を見る
    </a>
    <p style="font-size:11px; color:#999; margin-top:12px;">
        このメールはX有名人モニタリングシステムにより自動送信されています
    </p>
</div>
"""
        # </body>タグの前にフッターを挿入
        html_content = html_content.replace("</body>", footer_html + "</body>")

    for recipient in recipients:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = gmail_user
        msg["To"] = recipient

        # プレーンテキスト版（フォールバック）
        text_lines = [
            f"{type_label}レポート（{today}）",
            "",
            "このメールはHTML形式です。HTML対応のメールクライアントでご覧ください。",
        ]
        if share_link:
            text_lines.extend([
                "",
                "---",
                "過去のレポートはこちらからいつでもご覧いただけます:",
                share_link,
            ])

        text_part = MIMEText("\n".join(text_lines), "plain", "utf-8")
        html_part = MIMEText(html_content, "html", "utf-8")

        msg.attach(text_part)
        msg.attach(html_part)

        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(gmail_user, gmail_password)
                server.send_message(msg)
            print(f"  ✓ 送信完了: {recipient}")
        except Exception as e:
            print(f"  ✗ 送信失敗 ({recipient}): {e}")


def collect_recipients(analyzed_data):
    """分析データから全送信先を収集する"""
    all_recipients = set()
    for data in analyzed_data.values():
        for r in data["target"].get("recipients", []):
            all_recipients.add(r)
    return list(all_recipients)


# テスト用
if __name__ == "__main__":
    print("sender.py - テストにはmain.pyを実行してください")
