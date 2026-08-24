"""AgentCore Gateway Lambda Target: 天気情報ツール（実 API 版）

OpenWeatherMap API を使って実際の天気データを取得する。
API Key は AgentCore Identity の Credential Provider から取得する。

環境変数:
    OPENWEATHERMAP_API_KEY: OpenWeatherMap API Key
        (AgentCore Runtime の環境変数 or Lambda 環境変数で設定)
"""

import json
import os
import urllib.request
import urllib.error
import urllib.parse

OPENWEATHERMAP_API_KEY = os.environ.get("OPENWEATHERMAP_API_KEY", "")
BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

# 日本の都市名 → 英語名マッピング
CITY_MAP = {
    "東京": "Tokyo",
    "大阪": "Osaka",
    "名古屋": "Nagoya",
    "福岡": "Fukuoka",
    "札幌": "Sapporo",
    "京都": "Kyoto",
    "横浜": "Yokohama",
    "神戸": "Kobe",
    "新宿": "Shinjuku",
    "渋谷": "Shibuya",
}

# 天気コンディション → 日本語
CONDITION_MAP = {
    "Clear": "晴れ",
    "Clouds": "曇り",
    "Rain": "雨",
    "Drizzle": "小雨",
    "Thunderstorm": "雷雨",
    "Snow": "雪",
    "Mist": "霧",
    "Fog": "濃霧",
}


def get_weather(location: str) -> str:
    """OpenWeatherMap API で天気情報を取得する。"""
    if not OPENWEATHERMAP_API_KEY:
        return f"⚠️ API Key が設定されていません。OPENWEATHERMAP_API_KEY 環境変数を確認してください。"

    # 都市名を英語に変換（マッピングになければそのまま使用）
    city = CITY_MAP.get(location, location)

    params = urllib.parse.urlencode({
        "q": city,
        "appid": OPENWEATHERMAP_API_KEY,
        "units": "metric",
        "lang": "ja",
    })

    url = f"{BASE_URL}?{params}"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())

        temp = data["main"]["temp"]
        humidity = data["main"]["humidity"]
        condition_en = data["weather"][0]["main"]
        description = data["weather"][0]["description"]
        wind_speed = data["wind"]["speed"]
        wind_deg = data["wind"].get("deg", 0)

        # 風向きを方角に変換
        directions = ["北", "北東", "東", "南東", "南", "南西", "西", "北西"]
        wind_dir = directions[int((wind_deg + 22.5) / 45) % 8]

        condition_ja = CONDITION_MAP.get(condition_en, description)

        return (
            f"🌤️ {location} の天気情報（リアルタイム）:\n"
            f"  気温: {temp:.1f}℃\n"
            f"  天候: {condition_ja}（{description}）\n"
            f"  湿度: {humidity}%\n"
            f"  風: {wind_dir} {wind_speed}m/s"
        )

    except urllib.error.HTTPError as e:
        if e.code == 401:
            return "⚠️ API Key が無効です。OpenWeatherMap のアカウントを確認してください。"
        elif e.code == 404:
            return f"⚠️ 都市 '{location}' ({city}) が見つかりません。"
        else:
            return f"⚠️ API エラー: HTTP {e.code}"
    except Exception as e:
        return f"⚠️ 天気情報の取得に失敗しました: {str(e)}"


def lambda_handler(event, context):
    """Lambda エントリーポイント。"""
    tool_name = event.get("name", "")
    tool_input = event.get("input", {})

    if tool_name == "get_weather":
        result = get_weather(tool_input.get("location", ""))
    else:
        result = f"Unknown tool: {tool_name}"

    return {"output": result}
