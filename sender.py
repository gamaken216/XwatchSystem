"""
メール配信モジュール
====================
Gmail SMTPでメール用HTMLを送信する。
メール本文: 全体要約 + 注目ツイート + ウェブ版リンク
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime


def send_report(gmail_user, gmail_password, recipients, email_html, report_type="daily"):
    """
    メール用HTMLをメールで送信する。

    Args:
        gmail_user: Gmailアドレス
        gmail_password: アプリパスワード
        recipients: 送信先リスト
        email_html: reporter.generate_email_html() の戻り値（HTML文字列）
        report_type: "daily" or "weekly"
    """
    today = datetime.now().strftime("%Y年%m月%d日")
    type_label = "日次" if report_type == "daily" else "週次"
    subject = f"【X モニタリング】{type_label}レポート - {today}"

    for recipient in recipients:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = gmail_user
        msg["To"] = recipient

        text_part = MIMEText(
            f"{type_label}レポート（{today}）\nHTML対応のメールクライアントでご覧ください。",
            "plain", "utf-8"
        )
        html_part = MIMEText(email_html, "html", "utf-8")

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
