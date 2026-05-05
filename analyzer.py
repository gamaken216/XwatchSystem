"""
AI分析モジュール
================
Google Gemini APIを使ってツイートの感情分析・カテゴリ分類・要約を行う。
"""
import json
import time
from datetime import datetime


class QuotaExhaustedError(Exception):
    """無料枠のAPI上限に達した場合の例外"""
    pass


def analyze_tweets(api_key, model, target, tweets):
    """
    対象人物のツイート群をGemini AIで分析する。

    Returns:
        dict: {
            "summary": str,          # 全体要約
            "sentiment": {           # 感情分析の集計
                "positive": int,
                "negative": int,
                "neutral": int,
            },
            "categories": dict,      # カテゴリ別件数
            "top_tweets": list,      # 注目ツイートTop5
            "alert": str or None,    # 炎上リスク等のアラート
            "tweet_details": list,   # 各ツイートの分析結果
        }
    """
    if not tweets:
        return {
            "summary": "本日の該当ツイートはありませんでした。",
            "sentiment": {"positive": 0, "negative": 0, "neutral": 0},
            "categories": {},
            "top_tweets": [],
            "alert": None,
            "tweet_details": [],
        }

    from google import genai

    client = genai.Client(api_key=api_key)
    today = datetime.now().strftime("%Y年%m月%d日")

    # ツイートデータをテキスト化（最大100件に制限してAPIエラーを防ぐ）
    tweets_for_analysis = tweets[:100]
    tweets_text = ""
    for i, tw in enumerate(tweets_for_analysis, 1):
        tweets_text += (
            f"[{i}] @{tw['user']} ({tw['created_at']})\n"
            f"{tw['text']}\n"
            f"いいね:{tw['favorite_count']} RT:{tw['retweet_count']}\n"
            f"---\n"
        )

    prompt = f"""あなたはSNS分析の専門家です。
以下は「{target['name']}」に関するX（旧Twitter）の投稿データ（{today}取得分、{len(tweets_for_analysis)}件）です。

以下のJSON形式で分析結果を返してください。JSONのみを返し、他の文字は含めないでください。

{{
    "summary": "全体の傾向を3-5文で要約",
    "sentiment": {{
        "positive": ポジティブなツイート数,
        "negative": ネガティブなツイート数,
        "neutral": ニュートラルなツイート数
    }},
    "categories": {{
        "カテゴリ名": 件数
    }},
    "top_tweets": [
        {{
            "index": ツイート番号,
            "reason": "注目理由を1文で",
            "sentiment": "positive/negative/neutral"
        }}
    ],
    "alert": "炎上リスクや急激な変化があれば記載。なければnull",
    "tweet_details": [
        {{
            "index": ツイート番号,
            "sentiment": "positive/negative/neutral",
            "category": "カテゴリ名"
        }}
    ]
}}

カテゴリは以下から適切なものを使用（複数可、該当なしは「その他」）:
- 新刊・作品情報
- イベント・出演情報
- スキャンダル・ゴシップ
- ファンの反応・応援
- ニュース・報道
- 日常・プライベート
- その他

注目ツイートは、いいね数・RT数が多いもの、または内容が特に重要なものを最大5件選んでください。

=== ツイートデータ ===
{tweets_text}
"""

    max_retries = 6
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
            )

            # JSON部分を抽出してパース
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                text = text.rsplit("```", 1)[0]

            result = json.loads(text)
            return result

        except Exception as e:
            error_str = str(e)
            # 429/503/レート制限は一時エラーとしてリトライ（FreeTier表記含む）
            is_retryable = "503" in error_str or "429" in error_str or "UNAVAILABLE" in error_str or "RESOURCE_EXHAUSTED" in error_str
            if is_retryable and attempt < max_retries - 1:
                wait_sec = min(60 * (2 ** attempt), 600)
                print(f"  API一時エラー（リトライ {attempt+1}/{max_retries}、{wait_sec}秒後）: {e}")
                time.sleep(wait_sec)
                continue
            # リトライ不可またはリトライ上限到達で、日次クォータ超過の場合
            is_free_tier_exhausted = "FreeTier" in error_str or "free_tier" in error_str
            if is_free_tier_exhausted:
                print(f"  ⚠ 無料枠のAPI上限に到達しました。残りの分析をスキップします。")
                raise QuotaExhaustedError(error_str)
            print(f"  AI分析エラー: {e}")
            return {
                "summary": f"分析中にエラーが発生しました: {str(e)}",
                "sentiment": {"positive": 0, "negative": 0, "neutral": 0},
                "categories": {},
                "top_tweets": [],
                "alert": None,
                "tweet_details": [],
            }


def analyze_all(api_key, model, collected_data):
    """全対象人物の分析を実行する"""
    results = {}
    skipped = []

    for tid, data in collected_data.items():
        target = data["target"]
        tweets = data["tweets"]
        print(f"\n  {target['name']} を分析中... ({len(tweets)}件)")

        try:
            analysis = analyze_tweets(api_key, model, target, tweets)
        except QuotaExhaustedError:
            # 残りの対象をスキップリストに追加
            skipped.append(target['name'])
            for remaining_tid, remaining_data in collected_data.items():
                if remaining_tid not in results and remaining_tid != tid:
                    skipped.append(remaining_data["target"]["name"])
                    results[remaining_tid] = {
                        "target": remaining_data["target"],
                        "tweets": remaining_data["tweets"],
                        "analysis": {
                            "summary": "API無料枠の上限により分析をスキップしました。",
                            "sentiment": {"positive": 0, "negative": 0, "neutral": 0},
                            "categories": {},
                            "top_tweets": [],
                            "alert": None,
                            "tweet_details": [],
                        },
                    }
            # 現在の対象も追加
            results[tid] = {
                "target": target,
                "tweets": tweets,
                "analysis": {
                    "summary": "API無料枠の上限により分析をスキップしました。",
                    "sentiment": {"positive": 0, "negative": 0, "neutral": 0},
                    "categories": {},
                    "top_tweets": [],
                    "alert": None,
                    "tweet_details": [],
                },
            }
            print(f"  ⚠ API無料枠の上限のため、以下の分析をスキップしました: {', '.join(skipped)}")
            break

        results[tid] = {
            "target": target,
            "tweets": tweets,
            "analysis": analysis,
        }

        print(f"    感情: +{analysis['sentiment']['positive']} "
              f"-{analysis['sentiment']['negative']} "
              f"={analysis['sentiment']['neutral']}")
        if analysis.get("alert"):
            print(f"    ⚠ アラート: {analysis['alert']}")

    return results


# テスト用
if __name__ == "__main__":
    print("analyzer.py - テストにはmain.pyを実行してください")
