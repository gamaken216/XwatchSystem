import asyncio
import json
from twikit import Client

async def test():
    with open('../x_summary2/settings.json', encoding='utf-8') as f:
        s = json.load(f)
    client = Client('ja-JP')
    client.set_cookies(s['x_cookies'])
    print("アカウントのツイートを直接取得...")
    try:
        # ユーザーを取得
        user = await client.get_user_by_screen_name('Shohei_Ohtani17')
        print(f"ユーザー取得: {user.name}")
        tweets = await user.get_tweets('Tweets', count=5)
        count = 0
        for t in tweets:
            print(f"[{count+1}] {t.text[:60]}")
            count += 1
        print(f"\n合計 {count} 件取得")
    except Exception as e:
        print(f"エラー: {e}")

asyncio.run(test())
