"""
ツイート収集モジュール
=====================
Playwrightを使ってキーワード検索でツイートを取得する。
"""
import asyncio
import json
import os
import re
import urllib.parse
from datetime import datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")


def load_targets():
    """targets.json から対象人物リストを読み込む"""
    path = os.path.join(SCRIPT_DIR, "targets.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [t for t in data["targets"] if t.get("enabled", True)]


def build_query(target):
    """対象人物の設定から検索クエリを構築する"""
    parts = []

    # キーワード（OR結合）
    if target.get("keywords"):
        kw_query = " OR ".join(f'"{kw}"' for kw in target["keywords"])
        parts.append(f"({kw_query})")

    # @メンション
    if target.get("x_account"):
        account = target["x_account"].lstrip("@")
        parts.append(f"@{account}")

    # 除外キーワード
    for ex in target.get("exclude_keywords", []):
        parts.append(f'-"{ex}"')

    query = " OR ".join(parts[:2])  # キーワードとメンションをOR
    excludes = " ".join(parts[2:])  # 除外はAND

    if excludes:
        query = f"{query} {excludes}"

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
                "name": name,
                "value": value,
                "domain": ".x.com",
                "path": "/",
                "secure": True,
                "httpOnly": True,
            })
    await context.add_cookies(cookie_list)
    return browser, context


async def _extract_tweets_from_page(page):
    """ページ上のツイート要素からデータを抽出する"""
    tweet_elements = await page.query_selector_all('article[data-testid="tweet"]')
    tweets = []
    for article in tweet_elements:
        try:
            screen_name = ""
            tweet_url = ""
            user_name = ""
            tweet_id = ""

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

            favorite_count = 0
            retweet_count = 0
            quote_count = 0

            if screen_name and text:
                tweets.append({
                    "id": tweet_id,
                    "user": screen_name,
                    "user_name": user_name,
                    "text": text,
                    "created_at": time_str,
                    "favorite_count": favorite_count,
                    "retweet_count": retweet_count,
                    "quote_count": quote_count,
                    "url": tweet_url,
                })
        except Exception:
            continue
    return tweets


async def search_tweets(cookies, target, max_tweets=100, interval_sec=5):
    """指定した対象人物に関するツイートを検索・取得する"""
    from playwright.async_api import async_playwright

    query = build_query(target)
    print(f"  検索クエリ: {query}")

    encoded_query = urllib.parse.quote(query)
    search_url = f"https://x.com/search?q={encoded_query}&src=typed_query&f=live"

    tweets = []
    async with async_playwright() as p:
        browser, context = await _create_browser_context(p, cookies)
        page = await context.new_page()

        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_selector('article[data-testid="tweet"]', timeout=20000)
            await page.wait_for_timeout(2000)

            tweets = await _extract_tweets_from_page(page)

            scroll_attempts = 0
            max_scrolls = max(1, max_tweets // 10)
            while len(tweets) < max_tweets and scroll_attempts < max_scrolls:
                prev_count = len(tweets)
                await page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
                await page.wait_for_timeout(2000)
                tweets = await _extract_tweets_from_page(page)
                scroll_attempts += 1
                if len(tweets) == prev_count:
                    break

        except Exception as e:
            print(f"  エラー: {e}")
        finally:
            await browser.close()

    seen_ids = set()
    unique_tweets = []
    for t in tweets:
        if t["id"] and t["id"] not in seen_ids:
            seen_ids.add(t["id"])
            unique_tweets.append(t)

    return unique_tweets[:max_tweets]


def remove_duplicates(tweets, history_file):
    """
    同日内の重複実行時のみツイートを除外する。
    historyファイルに「今日の日付」が記録されていれば引き続き使用し、
    日付が変わっていれば（=翌日の実行）リセットして全件新規扱いにする。
    """
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


async def collect_all(cookies, targets, max_tweets=100, interval_sec=5):
    """全対象人物のツイートを収集する"""
    os.makedirs(DATA_DIR, exist_ok=True)
    results = {}

    for i, target in enumerate(targets):
        name = target["name"]
        print(f"\n[{i+1}/{len(targets)}] {name} のツイートを収集中...")

        tweets = await search_tweets(cookies, target, max_tweets, interval_sec)
        print(f"  → {len(tweets)}件取得")

        history_file = os.path.join(DATA_DIR, f"history_{target['id']}.json")
        new_tweets = remove_duplicates(tweets, history_file)
        print(f"  → {len(new_tweets)}件が新規")

        results[target["id"]] = {
            "target": target,
            "tweets": new_tweets,
            "total_found": len(tweets),
            "new_count": len(new_tweets),
        }

        if i < len(targets) - 1:
            print(f"  {interval_sec}秒待機中...")
            await asyncio.sleep(interval_sec)

    return results


# テスト用
if __name__ == "__main__":
    from config import X_COOKIES, MAX_TWEETS_PER_PERSON, SEARCH_INTERVAL_SEC

    targets = load_targets()
    print(f"対象人物: {len(targets)}名")

    for t in targets:
        print(f"  - {t['name']}: {build_query(t)}")

    results = asyncio.run(
        collect_all(X_COOKIES, targets, MAX_TWEETS_PER_PERSON, SEARCH_INTERVAL_SEC)
    )

    for tid, data in results.items():
        print(f"\n{data['target']['name']}: {data['new_count']}件の新規ツイート")
