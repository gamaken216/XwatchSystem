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
    """指定した対象人物に関するツイートを検索・取得する"""
    from playwright.async_api import async_playwright

    query = build_query(target)
    print(f"  検索クエリ: {query}")
    encoded_query = urllib.parse.quote(query)
    search_url = f"https://x.com/search?q={encoded_query}&src=typed_query&f=live"

    # IDをキーにした辞書で蓄積（仮想スクロールで消えても失わない）
    all_tweets = {}

    async with async_playwright() as p:
        browser, context = await _create_browser_context(p, cookies)
        page = await context.new_page()
        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)

            # ツイートが表示されるか、検索結果なしの表示が出るかを待つ
            tweet_or_empty = await page.wait_for_selector(
                'article[data-testid="tweet"], '
                '[data-testid="empty_state_header_text"], '
                '[data-testid="emptyState"]',
                timeout=30000,
                state="attached",
            )
            # 検索結果なしの場合は正常終了
            if tweet_or_empty:
                tag = await tweet_or_empty.get_attribute("data-testid")
                if tag in ("empty_state_header_text", "emptyState"):
                    print("  検索結果なし（0件）")
                    await browser.close()
                    return []

            await page.wait_for_timeout(2000)

            no_new_count = 0  # 新規ツイートが増えない回数
            max_scrolls = 50  # 最大50回スクロール

            for _ in range(max_scrolls):
                # 現在表示されているツイートを取得して蓄積
                visible = await _extract_tweets_from_page(page)
                prev_count = len(all_tweets)
                for tw in visible:
                    if tw["id"] and tw["id"] not in all_tweets:
                        all_tweets[tw["id"]] = tw

                if len(all_tweets) >= max_tweets:
                    break

                # 新規が増えなかった回数をカウント
                if len(all_tweets) == prev_count:
                    no_new_count += 1
                    if no_new_count >= 3:
                        break  # 3回連続で増えなければ終了
                else:
                    no_new_count = 0

                # スクロールして次のツイートを読み込む
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(2500)

        except Exception as e:
            print(f"  エラー: {e}")
        finally:
            await browser.close()

    result = list(all_tweets.values())
    print(f"  スクロール収集: {len(result)}件")
    return result[:max_tweets]


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
            "target": target, "tweets": new_tweets,
            "total_found": len(tweets), "new_count": len(new_tweets),
        }
        if i < len(targets) - 1:
            # レート制限対策: 5件ごとに長めの待機を入れる
            if (i + 1) % 5 == 0:
                wait = interval_sec * 4
                print(f"  レート制限対策: {wait}秒待機中...")
            else:
                wait = interval_sec
                print(f"  {wait}秒待機中...")
            await asyncio.sleep(wait)
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
