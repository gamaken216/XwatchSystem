"""
X有名人モニタリングシステム - メインスクリプト
================================================
全モジュールを統合して実行する。

使い方:
    python main.py           # 日次レポート
    python main.py --weekly  # 週次レポート
    python main.py --test    # テスト実行（メール送信なし）
"""
import asyncio
import sys
import os
import io
import json
import logging
from datetime import datetime

# Windows環境のUTF-8対応
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")

# ログ設定
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(
            os.path.join(LOG_DIR, f"run_{datetime.now():%Y%m%d_%H%M%S}.log"),
            encoding="utf-8",
        ),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def load_config():
    """環境変数またはconfig.pyから設定を読み込む"""

    # X Cookies
    x_cookies_env = os.environ.get("X_COOKIES_JSON")
    if x_cookies_env:
        X_COOKIES = json.loads(x_cookies_env)
    else:
        try:
            from config import X_COOKIES
        except ImportError:
            logger.error("X_COOKIES_JSON 環境変数が設定されていません。")
            return None

    # Gemini API Key
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        try:
            from config import GEMINI_API_KEY
        except ImportError:
            logger.error("GEMINI_API_KEY 環境変数が設定されていません。")
            return None

    # Gmail
    GMAIL_USER = os.environ.get("GMAIL_USER")
    if not GMAIL_USER:
        try:
            from config import GMAIL_USER
        except ImportError:
            logger.error("GMAIL_USER 環境変数が設定されていません。")
            return None

    GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
    if not GMAIL_APP_PASSWORD:
        try:
            from config import GMAIL_APP_PASSWORD
        except ImportError:
            logger.error("GMAIL_APP_PASSWORD 環境変数が設定されていません。")
            return None

    # 受信者リスト（Secretsまたはconfig.pyから取得）
    RECIPIENTS_ENV = os.environ.get("REPORT_RECIPIENTS", "")
    if RECIPIENTS_ENV:
        RECIPIENTS = [r.strip() for r in RECIPIENTS_ENV.split(",") if r.strip()]
    else:
        try:
            from config import REPORT_RECIPIENTS
            RECIPIENTS = [r.strip() for r in REPORT_RECIPIENTS.split(",") if r.strip()]
        except ImportError:
            RECIPIENTS = []

    # その他設定
    GEMINI_MODEL = "gemini-2.5-flash"
    MAX_TWEETS_PER_PERSON = 300
    SEARCH_INTERVAL_SEC = 5

    return {
        "X_COOKIES": X_COOKIES,
        "GEMINI_API_KEY": GEMINI_API_KEY,
        "GEMINI_MODEL": GEMINI_MODEL,
        "GMAIL_USER": GMAIL_USER,
        "GMAIL_APP_PASSWORD": GMAIL_APP_PASSWORD,
        "RECIPIENTS": RECIPIENTS,
        "MAX_TWEETS_PER_PERSON": MAX_TWEETS_PER_PERSON,
        "SEARCH_INTERVAL_SEC": SEARCH_INTERVAL_SEC,
    }


def main():
    # 引数チェック
    args = sys.argv[1:]
    report_type = "weekly" if "--weekly" in args else "daily"
    test_mode = "--test" in args

    logger.info("=" * 60)
    logger.info(f"X有名人モニタリングシステム 起動")
    logger.info(f"レポートタイプ: {report_type}")
    logger.info(f"テストモード: {test_mode}")
    logger.info("=" * 60)

    # 設定読み込み
    cfg = load_config()
    if cfg is None:
        logger.error("設定の読み込みに失敗しました。終了します。")
        return

    X_COOKIES = cfg["X_COOKIES"]
    GEMINI_API_KEY = cfg["GEMINI_API_KEY"]
    GEMINI_MODEL = cfg["GEMINI_MODEL"]
    GMAIL_USER = cfg["GMAIL_USER"]
    GMAIL_APP_PASSWORD = cfg["GMAIL_APP_PASSWORD"]
    RECIPIENTS = cfg["RECIPIENTS"]
    MAX_TWEETS_PER_PERSON = cfg["MAX_TWEETS_PER_PERSON"]
    SEARCH_INTERVAL_SEC = cfg["SEARCH_INTERVAL_SEC"]

    from collector import load_targets, collect_all
    from analyzer import analyze_all
    from reporter import generate_web_report, generate_email_html
    from sender import send_report, collect_recipients

    # Step 1: 対象人物の読み込み
    logger.info("\n[Step 1/4] 対象人物の読み込み")
    targets = load_targets()
    if not targets:
        logger.warning("有効な対象人物がいません。targets.json を確認してください。")
        return
    logger.info(f"  対象人物: {len(targets)}名")
    for t in targets:
        logger.info(f"    - {t['name']} ({t.get('category', 'N/A')})")

    # Step 2: ツイート収集
    logger.info("\n[Step 2/4] ツイート収集")
    collected = asyncio.run(
        collect_all(X_COOKIES, targets, MAX_TWEETS_PER_PERSON, SEARCH_INTERVAL_SEC)
    )
    total = sum(d["new_count"] for d in collected.values())
    logger.info(f"  合計: {total}件の新規ツイート")

    if total == 0:
        logger.info("  新規ツイートが0件のため、レポートをスキップします。")
        return

    # Step 3: AI分析
    logger.info("\n[Step 3/4] AI分析")
    analyzed = analyze_all(GEMINI_API_KEY, GEMINI_MODEL, collected)

    # Step 4: レポート生成・配信
    logger.info("\n[Step 4/4] レポート生成・配信")

    # ウェブ用レポート生成（GitHub Pages公開用）
    web_report_path = generate_web_report(analyzed, report_type)
    logger.info(f"  ウェブレポート: {web_report_path}")

    # メール用HTML生成
    email_html = generate_email_html(analyzed, report_type)

    if test_mode:
        logger.info("  テストモードのためメール送信をスキップ")
        logger.info(f"  ウェブレポートを確認: {web_report_path}")
    else:
        # Secretsのアドレスを優先、なければtargets.jsonから取得
        recipients = RECIPIENTS if RECIPIENTS else collect_recipients(analyzed)
        if recipients:
            logger.info(f"  送信先: {len(recipients)}名")
            send_report(GMAIL_USER, GMAIL_APP_PASSWORD, recipients, email_html, report_type)
        else:
            logger.warning("  送信先が設定されていません。")

    logger.info("\n" + "=" * 60)
    logger.info("処理完了")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
