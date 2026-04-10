"""
メール配信モジュール
====================
Gmail SMTPでメール用HTMLを送信する。
・同じ client を持つターゲットの結果を1通にまとめて送信する。
・client が未設定のターゲットは "default" クライアントとして扱う。
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from collections import defaultdict


def group_by_client(analyzed_data):
    """
    analyzed_data を client フィールドでグループ化する。
    戻り値: { client_id: { target_id: data, ... }, ... }
    """
    groups = defaultdict(dict)
    for tid, data in analyzed_data.items():
        client = data["target"].get("client", "default")
        groups[client][tid] = data
    return groups


def collect_recipients_for_client(client_data):
    """あるクライアントグループの全送信先をまとめて返す"""
    all_recipients = set()
    for data in client_data.values():
        for r in data["target"].get("recipients", []):
            all_recipients.add(r)
    return list(all_recipients)


def send_report(gmail_user, gmail_password, recipients, email_html, report_type="daily"):
    """
    メール用HTMLをメールで送信する（単一クライアント向け）。

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


def send_all_reports(gmail_user, gmail_password, global_recipients,
                     analyzed_data, report_type, generate_email_html_fn):
    """
    クライアント別にメールをまとめて送信する。

    - global_recipients: settings.json 等で指定された全体宛先（全クライアント共通）
    - analyzed_data の各ターゲットに client フィールドがあれば、
      同一 client を1通にまとめて送信する。
    - 各クライアントには target["recipients"] の個別宛先も使用する。

    Args:
        gmail_user: Gmailアドレス
        gmail_password: アプリパスワード
        global_recipients: 全体共通の宛先リスト
        analyzed_data: analyze_all() の戻り値
        report_type: "daily" or "weekly"
        generate_email_html_fn: reporter.generate_email_html 関数への参照
    """
    groups = group_by_client(analyzed_data)
    today = datetime.now().strftime("%Y年%m月%d日")
    type_label = "日次" if report_type == "daily" else "週次"
    subject = f"【X モニタリング】{type_label}レポート - {today}"

    for client_id, client_data in groups.items():
        # 宛先: グローバル宛先 ＋ クライアント個別宛先
        per_target_recipients = collect_recipients_for_client(client_data)
        recipients = list(set(global_recipients) | set(per_target_recipients))

        if not recipients:
            print(f"  ⚠ クライアント '{client_id}': 送信先なし。スキップ。")
            continue

        # クライアントに属するターゲットだけでメールHTML生成
        email_html = generate_email_html_fn(client_data, report_type)

        target_names = "、".join(d["target"]["name"] for d in client_data.values())
        print(f"  クライアント '{client_id}' ({target_names}) → {len(recipients)}名に送信")

        for recipient in recipients:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = gmail_user
            msg["To"] = recipient
            msg.attach(MIMEText(
                f"{type_label}レポート（{today}）\nHTML対応のメールクライアントでご覧ください。",
                "plain", "utf-8"
            ))
            msg.attach(MIMEText(email_html, "html", "utf-8"))

            try:
                with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                    server.login(gmail_user, gmail_password)
                    server.send_message(msg)
                print(f"    ✓ 送信完了: {recipient}")
            except Exception as e:
                print(f"    ✗ 送信失敗 ({recipient}): {e}")


def collect_recipients(analyzed_data):
    """後方互換用: 全ターゲットの recipients を統合して返す"""
    all_recipients = set()
    for data in analyzed_data.values():
        for r in data["target"].get("recipients", []):
            all_recipients.add(r)
    return list(all_recipients)
