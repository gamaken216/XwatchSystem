import asyncio
import json
from playwright.async_api import async_playwright


async def test():
    with open('../x-summary2/settings.json', encoding='utf-8') as f:
        s = json.load(f)
    cookies = s['x_cookies']

    print("Playwright で検索テスト...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            locale="ja-JP",
        )
        cookie_list = []
        for name in ("auth_token", "ct0", "twid"):
            value = cookies.get(name, "")
            if value:
                cookie_list.append({"name": name, "value": value, "domain": ".x.com", "path": "/", "secure": True, "httpOnly": True})
        await context.add_cookies(cookie_list)

        page = await context.new_page()
        await page.goto("https://x.com/Shohei_Ohtani17", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_selector('article[data-testid="tweet"]', timeout=20000)

        tweets = await page.query_selector_all('article[data-testid="tweet"]')
        count = 0
        for article in tweets[:5]:
            text_el = await article.query_selector('[data-testid="tweetText"]')
            text = await text_el.inner_text() if text_el else "(no text)"
            count += 1
            print(f"[{count}] {text[:60]}")

        print(f"\n合計 {count} 件取得")
        await browser.close()

asyncio.run(test())
