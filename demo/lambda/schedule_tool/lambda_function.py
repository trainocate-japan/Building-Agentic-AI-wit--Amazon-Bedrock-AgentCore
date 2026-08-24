"""AgentCore Gateway Lambda Target: スケジュール取得ツール

山下光洋のプロフィールページ (yamamanx.com/profile/) から
スケジュール情報をリアルタイムでスクレイピングして返す。

ツール:
    - get_schedule: プロフィールページからスケジュールを取得
"""

import re
import urllib.request
from datetime import datetime
from html.parser import HTMLParser

PROFILE_URL = "https://www.yamamanx.com/profile/"


class TextExtractor(HTMLParser):
    """HTML からテキストを抽出するシンプルなパーサー。"""

    def __init__(self):
        super().__init__()
        self.texts = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip = True

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            stripped = data.strip()
            if stripped:
                self.texts.append(stripped)


def fetch_schedule_from_web() -> list[dict]:
    """プロフィールページからスケジュールを取得する。"""
    try:
        req = urllib.request.Request(
            PROFILE_URL,
            headers={"User-Agent": "AgentCore-Secretary-Agent/1.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode("utf-8")

        # HTMLからテキスト抽出
        parser = TextExtractor()
        parser.feed(html)
        lines = parser.texts

        # スケジュールセクションを探す
        schedule_start = None
        for i, line in enumerate(lines):
            if "セミナー登壇" in line and "スケジュール" in line:
                schedule_start = i + 1
                break

        if schedule_start is None:
            return []

        # スケジュール項目をパース
        # パターン: "7/22(水)" or "7/22(水)-7/24(金)" or "8/12(水)-14(金)"
        date_pattern = re.compile(
            r"^(\d{1,2})/(\d{1,2})\([月火水木金土日]\)"
        )

        events = []
        i = schedule_start
        while i < len(lines):
            line = lines[i]

            # "History" セクションに達したら終了
            if line == "History":
                break

            # 日付行の検出
            match = date_pattern.match(line)
            if match:
                date_str = line
                # 次の行がイベント名
                title = lines[i + 1] if i + 1 < len(lines) else ""
                # その次の行が説明
                description = lines[i + 2] if i + 2 < len(lines) else ""

                # 次のイベントの日付かどうかチェック
                if date_pattern.match(description):
                    description = ""
                    i += 2
                else:
                    i += 3

                events.append({
                    "date": date_str,
                    "title": title,
                    "description": description,
                })
            else:
                i += 1

        return events

    except Exception as e:
        return [{"date": "Error", "title": f"スケジュール取得エラー: {str(e)}", "description": ""}]


def get_schedule(date: str = "") -> str:
    """スケジュールを取得する。

    date が指定されていれば該当日のみ、なければ全件返す。
    """
    events = fetch_schedule_from_web()

    if not events:
        return "スケジュール情報を取得できませんでした。"

    # 日付フィルタ（指定された場合）
    if date:
        # "2026-08-05" → "8/5" の形式に変換して部分一致
        try:
            dt = datetime.strptime(date, "%Y-%m-%d")
            month_day = f"{dt.month}/{dt.day}"
            filtered = [e for e in events if month_day in e["date"]]
            if not filtered:
                return f"{date} のスケジュールは登録されていません。"
            events = filtered
        except ValueError:
            # フォーマットエラーなら全件返す
            pass

    # 整形して返す
    lines = ["📅 スケジュール:"]
    for event in events:
        lines.append(f"  {event['date']}")
        lines.append(f"    {event['title']}")
        if event["description"]:
            lines.append(f"    → {event['description']}")

    return "\n".join(lines)


def lambda_handler(event, context):
    """Lambda エントリーポイント。"""
    tool_name = event.get("name", "")
    tool_input = event.get("input", {})

    if tool_name == "get_schedule":
        result = get_schedule(tool_input.get("date", ""))
    else:
        result = f"Unknown tool: {tool_name}"

    return {"output": result}
