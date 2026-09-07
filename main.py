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

# Windows環境のUTF-8対応（pythonw.exe はstdoutがNullのためガード必要）
if sys.platform == "win32":
    if sys.stdout and hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    if sys.stderr and hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")

# ログ設定
os.makedirs(LOG_DIR, exist_ok=True)

# ログハンドラー（pythonw対応：StreamHandlerはstdoutがある場合のみ追加）
log_handlers = [
    logging.FileHandler(
        os.path.join(LOG_DIR, f"run_{datetime.now():%Y%m%d_%H%M%S}.log"),
        encoding="utf-8",
    )
]
if sys.stdout:
    log_handlers.append(logging.StreamHandler(sys.stdout))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=log_handlers,
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

    # 受信者リスト（環境変数 → settings.json → config.py の優先順）
    RECIPIENTS_ENV = os.environ.get("REPORT_RECIPIENTS", "")
    if RECIPIENTS_ENV:
        RECIPIENTS = [r.strip() for r in RECIPIENTS_ENV.split(",") if r.strip()]
    else:
        # settings.json の report_recipients を読む
        settings_file = os.path.join(SCRIPT_DIR, "settings.json")
        settings_recipients = ""
        if os.path.exists(settings_file):
            try:
                with open(settings_file, "r", encoding="utf-8") as f:
                    settings_data = json.load(f)
                settings_recipients = settings_data.get("report_recipients", "")
            except Exception:
                pass
        if settings_recipients:
            RECIPIENTS = [r.strip() for r in settings_recipients.split(",") if r.strip()]
        else:
            try:
                from config import REPORT_RECIPIENTS
                RECIPIENTS = [r.strip() for r in REPORT_RECIPIENTS.split(",") if r.strip()]
            except ImportError:
                RECIPIENTS = []

    # settings.json / config.py は .gitignore 対象でGitHub Actions上に存在せず、
    # ワークフローも REPORT_RECIPIENTS を渡していないため RECIPIENTS が空になる。
    # 日次レポートは targets.json 側の recipients で送られるので気づきにくいが、
    # アラートはこの RECIPIENTS を使うため、空だと異常を検知しても無言で止まる
    # （2026-09-05〜07の収集ゼロが3日間気づかれなかった原因）。targets.json から拾う。
    if not RECIPIENTS:
        try:
            targets_file = os.path.join(SCRIPT_DIR, "targets.json")
            with open(targets_file, "r", encoding="utf-8") as f:
                targets_data = json.load(f)
            fallback = set()
            for t in targets_data.get("targets", []):
                for r in t.get("recipients", []):
                    if r.strip():
                        fallback.add(r.strip())
            RECIPIENTS = sorted(fallback)
            if RECIPIENTS:
                logger.info(f"REPORT_RECIPIENTS未設定のため targets.json から宛先を補完: {len(RECIPIENTS)}件")
        except Exception as e:
            logger.warning(f"targets.json からの宛先補完に失敗: {e}")

    # その他設定
    # 2.0系はGoogleが無料枠を廃止（limit: 0）したため使用不可（2026-06-11確認）。
    # 2.5-flash は無料枠RPDが小さくすぐ枯渇するため、RPDの大きい 2.5-flash-lite を使う。
    GEMINI_MODEL = "gemini-2.5-flash-lite"
    MAX_TWEETS_PER_PERSON = 100
    SEARCH_INTERVAL_SEC = 15

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


LAST_RUN_FILE = os.path.join(SCRIPT_DIR, ".last_run")


def _already_ran_today(report_type):
    """今日すでに同じ種類のレポートを送ったかを .last_run で判定する"""
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        with open(LAST_RUN_FILE, "r", encoding="utf-8") as f:
            return f.read().strip() == f"{today} {report_type}"
    except OSError:
        return False


def _mark_ran_today(report_type):
    """レポート送信完了を .last_run に記録する"""
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        with open(LAST_RUN_FILE, "w", encoding="utf-8") as f:
            f.write(f"{today} {report_type}")
    except OSError as e:
        logger.warning(f"⚠️ .last_run の書き込みに失敗: {e}")


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

    # 同じ日に2通目を送らないための重複防止。
    # ローカル運用では3台のPCそれぞれにタスクを登録しており（どれか1台が
    # その日に起動していればレポートが出る）、フォルダはDropbox同期なので
    # このファイルも共有される。2台が同時刻に走ると二重配信になるため、
    # 実行時刻はPCごとにずらしてある。GitHub Actions上ではこのファイルが
    # チェックアウトに含まれない（.gitignore対象）ので影響しない。
    if not test_mode and _already_ran_today(report_type):
        logger.info(f"本日はすでに{report_type}レポートを送信済みです。スキップします。")
        return

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
    from sender import send_all_reports, collect_recipients, send_alert

    # Step 1: 対象人物の読み込み
    logger.info("\n[Step 1/4] 対象人物の読み込み")
    targets, days_back = load_targets()
    if not targets:
        logger.warning("有効な対象人物がいません。targets.json を確認してください。")
        return
    logger.info(f"  対象人物: {len(targets)}名")
    logger.info(f"  検索期間: 過去{days_back}日間")
    for t in targets:
        logger.info(f"    - {t['name']} ({t.get('category', 'N/A')})")

    # Step 2: ツイート収集
    logger.info("\n[Step 2/4] ツイート収集")
    collected = asyncio.run(
        collect_all(X_COOKIES, targets, MAX_TWEETS_PER_PERSON, SEARCH_INTERVAL_SEC, days_back)
    )
    total = sum(d["new_count"] for d in collected.values())
    logger.info(f"  合計: {total}件の新規ツイート")

    if total == 0:
        # state を集計して「収集失敗による0件」か「単に新規がない0件」かを切り分ける
        states = [d.get("state", "unknown") for d in collected.values()]
        failure_states = ("login", "error", "timeout", "exception")
        failed = [s for s in states if s in failure_states]

        if failed:
            # 収集が壊れている → 管理者に異常アラートを送る（静かに止まるのを防ぐ）
            if "login" in failed:
                reason = "Cookie失効の可能性（ログイン画面にリダイレクト）"
            elif failed.count("error") >= failed.count("timeout"):
                reason = "レート制限/エラー画面を検出"
            else:
                reason = "収集タイムアウト"

            detail_lines = ["対象ごとの収集結果:"]
            for d in collected.values():
                detail_lines.append(
                    f"  - {d['target']['name']}: state={d.get('state', 'unknown')} / "
                    f"取得{d.get('total_found', 0)}件"
                )
            detail = "\n".join(detail_lines)

            logger.error(f"  収集失敗を検出（{reason}）。アラートメールを送信します。")
            if not test_mode:
                send_alert(GMAIL_USER, GMAIL_APP_PASSWORD, RECIPIENTS, reason, detail)
        else:
            logger.info("  新規ツイートが0件（収集は正常・新規投稿なし）のため、レポートをスキップします。")
        return

    # Step 3: AI分析
    logger.info("\n[Step 3/4] AI分析")
    analyzed = analyze_all(GEMINI_API_KEY, GEMINI_MODEL, collected)

    # Step 4: レポート生成・配信
    logger.info("\n[Step 4/4] レポート生成・配信")
    web_report_path = generate_web_report(analyzed, report_type)
    logger.info(f"  ウェブレポート: {web_report_path}")
    email_html = generate_email_html(analyzed, report_type)

    send_all_reports(
        GMAIL_USER, GMAIL_APP_PASSWORD, RECIPIENTS,
        analyzed, report_type, generate_email_html
    )
    if not test_mode:
        _mark_ran_today(report_type)

    logger.info("\n" + "=" * 60)
    logger.info("処理完了")
    logger.info("=" * 60)

    # ウェブレポートをGitHubに自動push
    if not test_mode:
        import subprocess
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            env = os.environ.copy()
            env["GIT_ASKPASS"] = "echo"
            env["GIT_TERMINAL_PROMPT"] = "0"

            # GitHub Actions環境ではGITHUB_TOKENで認証
            github_token = os.environ.get("GITHUB_TOKEN")
            if github_token:
                subprocess.run(
                    ["git", "-C", script_dir, "remote", "set-url", "origin",
                     f"https://x-access-token:{github_token}@github.com/gamaken216/XwatchSystem.git"],
                    check=True, env=env, capture_output=True
                )

            # git ユーザー情報を設定（GitHub Actions環境でのみ必要。
            # ローカル実行時に上書きすると本人の設定を壊すのでやらない）
            if github_token:
                subprocess.run(["git", "-C", script_dir, "config", "user.email", "action@github.com"], env=env, capture_output=True)
                subprocess.run(["git", "-C", script_dir, "config", "user.name", "GitHub Actions"], env=env, capture_output=True)

            subprocess.run(["git", "-C", script_dir, "add", "docs/"], check=True, env=env)
            result = subprocess.run(
                ["git", "-C", script_dir, "commit", "-m", f"レポート自動更新 {datetime.now().strftime('%Y-%m-%d')}"],
                env=env, capture_output=True, text=True, encoding="utf-8", errors="replace"
            )
            if result.returncode == 0 or "nothing to commit" in result.stdout:
                # ローカル実行だとリモートが先に進んでいてpushが弾かれることがある。
                # Dropbox上のリポジトリでrebaseは.git/rebase-mergeの削除に失敗するので
                # マージで取り込む。失敗してもpushは試す（弾かれたら次回に持ち越す）。
                pull = subprocess.run(
                    ["git", "-C", script_dir, "pull", "--no-rebase", "--no-edit", "origin", "master"],
                    env=env, capture_output=True, text=True, encoding="utf-8", errors="replace"
                )
                if pull.returncode != 0:
                    logger.warning(f"⚠️ pull に失敗（pushは試行します）: {pull.stderr.strip()[:200]}")
                subprocess.run(
                    ["git", "-C", script_dir, "push", "origin", "master"],
                    check=True, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace"
                )
                logger.info("✅ GitHub Pagesにウェブレポートを公開しました")
            else:
                logger.warning(f"⚠️ git commit失敗: {result.stderr}")
        except subprocess.CalledProcessError as e:
            logger.warning(f"⚠️ GitHub pushに失敗しました: {e}")


if __name__ == "__main__":
    main()
