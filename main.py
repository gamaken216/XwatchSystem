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
    try:
        from config import (
            X_COOKIES,
            GEMINI_API_KEY,
            GEMINI_MODEL,
            GMAIL_USER,
            GMAIL_APP_PASSWORD,
            MAX_TWEETS_PER_PERSON,
            SEARCH_INTERVAL_SEC,
        )
    except ImportError as e:
        logger.error(f"config.py の読み込みに失敗: {e}")
        logger.error("config.py を作成してください。")
        return

    from collector import load_targets, collect_all
    from analyzer import analyze_all
    from reporter import generate_html_report
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
    report_path = generate_html_report(analyzed, report_type)
    logger.info(f"  レポート: {report_path}")

    if test_mode:
        logger.info("  テストモードのためメール送信をスキップ")
        logger.info(f"  レポートを確認: {report_path}")
    else:
        recipients = collect_recipients(analyzed)
        if recipients:
            logger.info(f"  送信先: {len(recipients)}名")
            send_report(GMAIL_USER, GMAIL_APP_PASSWORD, recipients, report_path, report_type)
        else:
            logger.warning("  送信先が設定されていません。")

    logger.info("\n" + "=" * 60)
    logger.info("処理完了")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
