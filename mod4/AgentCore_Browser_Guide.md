# Amazon Bedrock AgentCore Browser 使い方ガイド

## AgentCore Browser とは

AgentCore Browser は、AIエージェントがWebサイトとインタラクションするための**フルマネージドなクラウドベースブラウザ**です。コンテナ化された安全な環境でChromeが動作し、エージェントがWebページのナビゲーション、フォーム入力、スクリーンショット取得、情報抽出などを行えます。

### 主な特徴

- **セッション分離**: コンテナ化された環境でブラウザが動作し、システムから隔離
- **Live View**: リアルタイムでブラウザ操作を監視可能
- **セッション録画・再生**: S3にDOM変更やユーザー操作を保存し、後から再生可能
- **スケーラブル**: 数千の同時セッションをサポート
- **フレームワーク連携**: Strands Agents、Nova Act、Playwright と統合

### ワークフロー

1. **Browser Toolの作成** — AWSマネージド（`aws.browser.v1`）またはカスタムブラウザを作成
2. **セッション開始** — タイムアウト付きの分離されたセッションを起動（デフォルト15分、最大8時間）
3. **ブラウザ操作** — WebSocket経由でナビゲーション・クリック・入力などを実行
4. **モニタリング** — Live ViewやCloudWatch Metricsで状態を確認

---

## 前提条件

### 必要な依存パッケージ

```bash
pip install bedrock-agentcore strands-agents strands-agents-tools playwright nest-asyncio boto3
```

### 必要なIAM権限

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock-agentcore:CreateBrowser",
        "bedrock-agentcore:ListBrowsers",
        "bedrock-agentcore:GetBrowser",
        "bedrock-agentcore:DeleteBrowser",
        "bedrock-agentcore:StartBrowserSession",
        "bedrock-agentcore:StopBrowserSession",
        "bedrock-agentcore:GetBrowserSession",
        "bedrock-agentcore:ListBrowserSessions",
        "bedrock-agentcore:ConnectBrowserAutomationStream",
        "bedrock-agentcore:ConnectBrowserLiveViewStream"
      ],
      "Resource": "arn:aws:bedrock-agentcore:<Region>:<ACCOUNT_ID>:browser/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": "*"
    }
  ]
}
```

---

## コードサンプル

### 1. Strands Agents を使った最もシンプルな例

```python
from strands import Agent
from strands_tools.browser import AgentCoreBrowser

# Browser Toolの初期化
browser_tool = AgentCoreBrowser(region="us-west-2")

# エージェントにBrowser Toolを渡す
agent = Agent(tools=[browser_tool.browser])

# Webサイトにアクセスして情報を取得
prompt = (
    "https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html "
    "にアクセスして、AgentCoreの主要機能をまとめてください。"
)

response = agent(prompt)
print(response.message["content"][0]["text"])
```

### 2. Playwright（非同期）で直接制御する例

LLMを使わず、プログラムからブラウザを直接操作する場合：

```python
from playwright.async_api import async_playwright, Playwright, BrowserType
from bedrock_agentcore.tools.browser_client import browser_session
import asyncio

async def run(playwright: Playwright):
    # AgentCoreのブラウザセッションを作成
    with browser_session('us-west-2') as client:
        # WebSocket URLと認証ヘッダーを取得
        ws_url, headers = client.generate_ws_headers()

        # リモートブラウザに接続
        chromium: BrowserType = playwright.chromium
        browser = await chromium.connect_over_cdp(
            ws_url,
            headers=headers
        )

        context = browser.contexts[0]
        page = context.pages[0]

        try:
            # Webサイトにナビゲート
            await page.goto("https://docs.aws.amazon.com/bedrock-agentcore/")
            title = await page.title()
            print(f"ページタイトル: {title}")

            # フォーム入力の例
            # await page.fill("#search-input", "AgentCore Browser")
            # await page.click("button[type='submit']")

            # スクリーンショット取得
            # await page.screenshot(path="screenshot.png")

            # セッションをLive Viewで確認できるよう待機
            await asyncio.sleep(120)
        finally:
            await page.close()
            await browser.close()

async def main():
    async with async_playwright() as playwright:
        await run(playwright)

if __name__ == "__main__":
    asyncio.run(main())
```

### 3. Playwright（同期）+ Live View Server

```python
from playwright.sync_api import sync_playwright, Playwright, BrowserType
from bedrock_agentcore.tools.browser_client import browser_session
from browser_viewer import BrowserViewerServer
import time

def run(playwright: Playwright):
    # ブラウザセッションを作成
    with browser_session('us-west-2') as client:
        ws_url, headers = client.generate_ws_headers()

        # ローカルでLive Viewサーバーを起動
        viewer = BrowserViewerServer(client, port=8005)
        viewer_url = viewer.start(open_browser=True)

        # Playwright で接続
        chromium: BrowserType = playwright.chromium
        browser = chromium.connect_over_cdp(
            ws_url,
            headers=headers
        )

        context = browser.contexts[0]
        page = context.pages[0]

        try:
            page.goto("https://amazon.com/")
            print(page.title())
            time.sleep(120)
        finally:
            page.close()
            browser.close()

with sync_playwright() as playwright:
    run(playwright)
```

### 4. カスタムブラウザの作成（録画機能付き）

```python
import boto3
import uuid

region = "us-west-2"
bucket = "your-recording-bucket"

client = boto3.client("bedrock-agentcore-control", region_name=region)

response = client.create_browser(
    name="MyRecordingBrowser",
    description="録画機能付きカスタムブラウザ",
    networkConfiguration={"networkMode": "PUBLIC"},
    executionRoleArn="arn:aws:iam::123456789012:role/AgentCoreBrowserRole",
    clientToken=str(uuid.uuid4()),
    recording={
        "enabled": True,
        "s3Location": {
            "bucket": bucket,
            "prefix": "browser-recordings"
        }
    }
)

browser_id = response.get("browserId")
print(f"作成されたブラウザID: {browser_id}")
print(f"録画保存先: s3://{bucket}/browser-recordings/")
```

### 5. カスタムブラウザを Strands Agent で使用

```python
from strands import Agent
from strands_tools.browser import AgentCoreBrowser

# カスタムブラウザのIDを指定
browser_identifier = "your-browser-identifier"
region = "us-west-2"

browser_tool = AgentCoreBrowser(region=region, identifier=browser_identifier)

agent = Agent(tools=[browser_tool.browser])
prompt = (
    "Navigate to https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html "
    "and summarize the key features of AgentCore."
)

response = agent(prompt)
print("Agent Response:")
print(response.message["content"][0]["text"])
```

### 6. TypeScript (Bedrock Converse API + Playwright)

```typescript
import { BedrockRuntimeClient, ConverseCommand } from '@aws-sdk/client-bedrock-runtime'
import { PlaywrightBrowser } from 'bedrock-agentcore/browser/playwright'

const browser = new PlaywrightBrowser({ region: 'us-west-2' })
await browser.startSession()

// ブラウザツール定義（navigate, click, type, getText等）
const browserTools = { /* JSON Schema定義 */ }

const bedrockClient = new BedrockRuntimeClient({ region: 'us-west-2' })
const messages: any[] = []
let step = 0
const maxSteps = 10

while (step < maxSteps) {
  const response = await bedrockClient.send(
    new ConverseCommand({
      modelId: 'anthropic.claude-sonnet-4-20250514-v1:0',
      system: [{ text: 'あなたはWebブラウザを操作するエージェントです。' }],
      messages,
      toolConfig: browserTools,
    })
  )

  if (response.stopReason === 'tool_use') {
    // ブラウザツールを実行し、結果を会話に追加
  } else {
    break // モデルの最終回答
  }
  step++
}
```

---

## Live View で確認する方法

1. [AgentCore コンソール](https://console.aws.amazon.com/bedrock-agentcore/home#) を開く
2. 左ナビゲーションで **Built-in tools** を選択
3. Browser Tool を選択
4. **Browser sessions** セクションで、ステータスが **Ready** のセッションを確認
5. **Live view / recording** 列の「View live session」リンクをクリック

---

## リソースの確認先

| # | リソース | 場所 |
|---|---|---|
| 1 | Live View | AgentCore Console > Tool Name > **View live session** |
| 2 | セッション録画・再生 | AgentCore Console > Tool Name > **View recording** |
| 3 | ブラウザログ | CloudWatch > Log groups > `/aws/bedrock-agentcore/browser/` |
| 4 | 録画ファイル | S3 > Your bucket > `browser-recordings/` prefix |
| 5 | カスタムブラウザ | AgentCore Console > **Built-in tools** > Your custom browser |

---

## ユースケース

| ユースケース | 説明 |
|---|---|
| Webリサーチ自動化 | APIのないサイトから最新情報を収集 |
| フォーム自動入力 | 業務アプリへのデータ入力を自動化 |
| Webテスト | AIが判断しながらE2Eテストを実行 |
| カスタマーサポート | Web上の情報を参照しながら回答 |
| 価格モニタリング | 競合サイトの価格変動を追跡 |
| データ収集・分析 | 複数サイトからの情報集約 |

---

## 参考リンク

- [公式ドキュメント: AgentCore Browser](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/browser-tool.html)
- [クイックスタート](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/browser-quickstart.html)
- [Playwright連携](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/browser-quickstart-playwright.html)
- [セッション録画](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/browser-session-recording.html)
- [AWSブログ: Introducing AgentCore Browser Tool](https://aws.amazon.com/blogs/machine-learning/introducing-amazon-bedrock-agentcore-browser-tool/)
