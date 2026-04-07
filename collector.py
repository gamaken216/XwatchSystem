"""
ツイート収集モジュール
=====================
twikitを使ってキーワード検索でツイートを取得する。
"""
import asyncio
import json
import os
from datetime import datetime, timedelta
from twikit import Client

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


async def search_tweets(cookies, target, max_tweets=100, interval_sec=5):
    """指定した対象人物に関するツイートを検索・取得する（複数ページ対応）"""
    client = Client("ja-JP")
    client.http.headers["User-Agent"] = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
    client.set_cookies(cookies)

    query = build_query(target)
    print(f"  検索クエリ: {query}")

    tweets = []
    try:
        results = await client.search_tweet(query, product="Latest", count=20)
        while results and len(tweets) < max_tweets:
            for tweet in results:
                tweets.append({
                    "id": tweet.id,
                    "user": tweet.user.screen_name,
                    "user_name": tweet.user.name,
                    "text": tweet.text,
                    "created_at": tweet.created_at,
                    "favorite_count": getattr(tweet, "favorite_count", 0),
                    "retweet_count": getattr(tweet, "retweet_count", 0),
                    "quote_count": getattr(tweet, "quote_count", 0),
                    "url": f"https://x.com/{tweet.user.screen_name}/status/{tweet.id}",
                })
            if len(tweets) >= max_tweets:
                break
            await asyncio.sleep(2)
            try:
                results = await results.next()
            except Exception:
                break
    except Exception as e:
        print(f"  エラー: {e}")

    return tweets[:max_tweets]


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
        # 今日のデータがあれば引き継ぐ、古ければリセット
        if data.get("date") == today:
            seen_ids = set(data.get("ids", []))
        # 日付が違う場合はseen_idsは空のまま（全件新規扱い）

    new_tweets = [t for t in tweets if t["id"] not in seen_ids]

    # 履歴を更新（今日の日付とIDを保存）
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

        # 重複排除
        history_file = os.path.join(DATA_DIR, f"history_{target['id']}.json")
        new_tweets = remove_duplicates(tweets, history_file)
        print(f"  → {len(new_tweets)}件が新規")

        results[target["id"]] = {
            "target": target,
            "tweets": new_tweets,
            "total_found": len(tweets),
            "new_count": len(new_tweets),
        }

        # レート制限回避
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
