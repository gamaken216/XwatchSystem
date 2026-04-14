"""
ツイート収集モジュール
=====================
Playwrightを使ってキーワード検索でツイートを取得する。
"""
import asyncio
import json
import os
import re
import time
import urllib.parse
from datetime import datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
DEBUG_DIR = os.path.join(SCRIPT_DIR, "logs", "debug")

# レート制限・エラー画面の検出用
LOGIN_URL_PATTERNS = ("/login", "/i/flow/login", "/account/access")
ERROR_TEXT_PATTERNS = (
    "Something went wrong",
    "Try reloading",
    "問題が発生しました",
    "再読み込み",
    "再試行",
    "Rate limit",
    "レート制限",
)


def load_targets():
    """targets.json から対象人物リストと設定を読み込む"""
    path = os.path.join(SCRIPT_DIR, "targets.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    targets = [t for t in data["targets"] if t.get("enabled", True)]
    days_back = data.get("days_back", 14)
    return targets, days_back


def build_query(target, days_back=14):
    """対象人物の設定から検索クエリを構築する（過去days_back日間に制限）"""
    search_parts = []
    if target.get("keywords"):
        kw_query = " OR ".join(f'"{kw}"' for kw in target["keywords"])
        search_parts.append(f"({kw_query})")
    if target.get("x_account"):
        account = target["x_account"].lstrip("@")
        search_parts.append(f"@{account}")
    query = " OR ".join(search_parts)
    for ex in target.get("exclude_keywords", []):
        query += f' -"{ex}"'
    # 過去2週間に制限
    since_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    query += f" since:{since_date}"
    return query


async def _create_browser_context(playwright, cookies):
    """Playwright のブラウザコンテキストを作成する"""
    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 900},
        locale="ja-JP",
    )
    cookie_list = []
    for name in ("auth_token", "ct0", "twid"):
        value = cookies.get(name, "")
        if value:
            cookie_list.append({
                "name": name, "value": value,
                "domain": ".x.com", "path": "/",
                "secure": True, "httpOnly": True,
            })
    await context.add_cookies(cookie_list)
    return browser, context


async def _dump_debug(page, target_id, reason):
    """失敗時のページ状態をスクショ+HTMLで保存する（GitHub Actionsのartifactで確認用）"""
    try:
        os.makedirs(DEBUG_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", str(target_id))
        prefix = os.path.join(DEBUG_DIR, f"{ts}_{safe_id}_{reason}")
        try:
            await page.screenshot(path=prefix + ".png", full_page=True)
        except Exception as e:
            print(f"  スクリーンショット失敗: {e}")
        try:
            html = await page.content()
            with open(prefix + ".html", "w", encoding="utf-8") as f:
                f.write(html)
        except Exception as e:
            print(f"  HTMLダンプ失敗: {e}")
        print(f"  デバッグ情報を保存: {prefix}.(png|html)")
    except Exception as e:
        print(f"  デバッグ情報の保存に失敗: {e}")


async def _classify_page(page):
    """現在のページ状態を分類する

    Returns:
        "tweets"  : ツイートが表示されている
        "empty"   : 検索結果なし
        "login"   : ログインページ（Cookie失効など）
        "error"   : "Something went wrong" 等のエラー画面（レート制限の可能性）
        "unknown" : まだ判別不能（読み込み中）
    """
    try:
        url = page.url or ""
    except Exception:
        url = ""
    for p in LOGIN_URL_PATTERNS:
        if p in url:
            return "login"

    if await page.query_selector('article[data-testid="tweet"]'):
        return "tweets"
    if await page.query_selector(
        '[data-testid="empty_state_header_text"], [data-testid="emptyState"]'
    ):
        return "empty"

    try:
        body_text = await page.inner_text("body", timeout=1000)
    except Exception:
        body_text = ""
    for t in ERROR_TEXT_PATTERNS:
        if t in body_text:
            return "error"
    return "unknown"


async def _wait_for_result_state(page, timeout_ms=30000, poll_ms=500):
    """tweets / empty / login / error のいずれかになるまで待機する"""
    deadline = time.monotonic() + timeout_ms / 1000
    last_state = "unknown"
    while time.monotonic() < deadline:
        state = await _classify_page(page)
        last_state = state
        if state != "unknown":
            return state
        await page.wait_for_timeout(poll_ms)
    return last_state


async def _extract_tweets_from_page(page):
    """ページ上の全ツイート要素からデータを抽出する"""
    tweet_elements = await page.query_selector_all('article[data-testid="tweet"]')
    tweets = []
    for article in tweet_elements:
        try:
            screen_name = tweet_id = tweet_url = user_name = ""
            user_link = await article.query_selector('a[role="link"][href*="/status/"]')
            if user_link:
                href = await user_link.get_attribute("href")
                if href and "/status/" in href:
                    parts = href.split("/")
                    status_idx = parts.index("status")
                    screen_name = parts[status_idx - 1]
                    tweet_id = parts[status_idx + 1]
                    tweet_url = f"https://x.com{href}"
            name_el = await article.query_selector('[data-testid="User-Name"] a span')
            if name_el:
                user_name = await name_el.inner_text()
            text_el = await article.query_selector('[data-testid="tweetText"]')
            text = await text_el.inner_text() if text_el else ""
            time_el = await article.query_selector("time")
            time_str = await time_el.get_attribute("datetime") if time_el else ""
            if screen_name and text:
                tweets.append({
                    "id": tweet_id, "user": screen_name, "user_name": user_name,
                    "text": text, "created_at": time_str,
                    "favorite_count": 0, "retweet_count": 0, "quote_count": 0,
                    "url": tweet_url,
                })
        except Exception:
            continue
    return tweets


async def search_tweets(cookies, target, max_tweets=100, interval_sec=5):
    """指定した対象人物に関するツイートを検索・取得する

    Returns:
        (tweets, state)
            tweets: list[dict]  取得したツイート
            state : "tweets" | "empty" | "login" | "error" | "timeout" | "exception"
    """
    from playwright.async_api import async_playwright

    days_back = target.get("_days_back", 14)
    query = build_query(target, days_back=days_back)
    print(f"  検索クエリ: {query}")
    encoded_query = urllib.parse.quote(query)
    search_url = f"https://x.com/search?q={encoded_query}&src=typed_query&f=live"

    all_tweets = {}
    final_state = "exception"

    async with async_playwright() as p:
        browser, context = await _create_browser_context(p, cookies)
        page = await context.new_page()
        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)

            state = await _wait_for_result_state(page, timeout_ms=30000)
            final_state = state

            if state == "empty":
                print("  検索結果なし（0件）")
                await browser.close()
                return [], "empty"

            if state == "login":
                print("  ログインページにリダイレクトされました（Cookie失効の可能性）")
                await _dump_debug(page, target.get("id", "unknown"), "login")
                await browser.close()
                return [], "login"

            if state == "error":
                print("  エラー画面を検出（レート制限の可能性）")
                await _dump_debug(page, target.get("id", "unknown"), "error")
                await browser.close()
                return [], "error"

            if state != "tweets":
                print(f"  タイムアウト（30秒）: ツイートもエラー画面も検出できず")
                await _dump_debug(page, target.get("id", "unknown"), "timeout")
                await browser.close()
                return [], "timeout"

            await page.wait_for_timeout(2000)

            no_new_count = 0
            max_scrolls = 50

            for _ in range(max_scrolls):
                visible = await _extract_tweets_from_page(page)
                prev_count = len(all_tweets)
                for tw in visible:
                    if tw["id"] and tw["id"] not in all_tweets:
                        all_tweets[tw["id"]] = tw

                if len(all_tweets) >= max_tweets:
                    break

                if len(all_tweets) == prev_count:
                    no_new_count += 1
                    if no_new_count >= 3:
                        break
                else:
                    no_new_count = 0

                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(2500)

            final_state = "tweets"

        except Exception as e:
            print(f"  エラー: {e}")
            try:
                await _dump_debug(page, target.get("id", "unknown"), "exception")
            except Exception:
                pass
            final_state = "exception"
        finally:
            try:
                await browser.close()
            except Exception:
                pass

    result = list(all_tweets.values())
    print(f"  スクロール収集: {len(result)}件")
    return result[:max_tweets], final_state


def remove_duplicates(tweets, history_file):
    """同日内の重複実行時のみツイートを除外する"""
    today = datetime.now().strftime("%Y-%m-%d")
    seen_ids = set()
    if os.path.exists(history_file):
        with open(history_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("date") == today:
            seen_ids = set(data.get("ids", []))
    new_tweets = [t for t in tweets if t["id"] not in seen_ids]
    seen_ids.update(t["id"] for t in new_tweets)
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump({"date": today, "ids": list(seen_ids)}, f)
    return new_tweets


async def collect_all(cookies, targets, max_tweets=100, interval_sec=5, days_back=14):
    """全対象人物のツイートを収集する

    連続失敗時は指数バックオフで待機を延ばし、3回連続で失敗したら中断する。
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    results = {}
    consecutive_failures = 0
    MAX_CONSECUTIVE_FAILURES = 3

    for i, target in enumerate(targets):
        name = target["name"]
        print(f"\n[{i+1}/{len(targets)}] {name} のツイートを収集中...")

        target["_days_back"] = days_back
        tweets, state = await search_tweets(cookies, target, max_tweets, interval_sec)
        print(f"  → {len(tweets)}件取得 (state={state})")

        history_file = os.path.join(DATA_DIR, f"history_{target['id']}.json")
        new_tweets = remove_duplicates(tweets, history_file)
        print(f"  → {len(new_tweets)}件が新規")
        results[target["id"]] = {
            "target": target, "tweets": new_tweets,
            "total_found": len(tweets), "new_count": len(new_tweets),
            "state": state,
        }

        is_failure = state in ("error", "timeout", "login", "exception")
        if state == "login":
            print("  Cookie失効の可能性が高いため、以降の収集を中止します")
            break

        if is_failure:
            consecutive_failures += 1
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                print(
                    f"  連続{MAX_CONSECUTIVE_FAILURES}回失敗したため、以降の収集を中止します"
                )
                break
        else:
            consecutive_failures = 0

        if i < len(targets) - 1:
            if is_failure:
                # 指数バックオフ: 60s, 90s, 120s (最大)
                wait = min(60 + 30 * (consecutive_failures - 1), 120)
                print(f"  失敗検出によるバックオフ: {wait}秒待機中...")
            elif (i + 1) % 5 == 0:
                wait = interval_sec * 10
                print(f"  レート制限対策: {wait}秒待機中...")
            else:
                wait = interval_sec
                print(f"  {wait}秒待機中...")
            await asyncio.sleep(wait)
    return results


# テスト用
if __name__ == "__main__":
    from config import X_COOKIES, MAX_TWEETS_PER_PERSON, SEARCH_INTERVAL_SEC
    targets, days_back = load_targets()
    print(f"対象人物: {len(targets)}名 / 検索期間: 過去{days_back}日間")
    for t in targets:
        print(f"  - {t['name']}: {build_query(t, days_back)}")
    results = asyncio.run(
        collect_all(X_COOKIES, targets, MAX_TWEETS_PER_PERSON, SEARCH_INTERVAL_SEC, days_back)
    )
    for tid, data in results.items():
        print(f"\n{data['target']['name']}: {data['new_count']}件の新規ツイート")
