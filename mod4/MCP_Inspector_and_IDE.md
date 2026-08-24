# ツールの一覧表示と起動 — インスペクター・IDE・フレームワーク

## 概要

AgentCore Gateway に登録されたツールを確認・実行する方法は3つあります：

| 方法 | 用途 | ユーザー |
|---|---|---|
| **エージェントフレームワーク** | プロダクションでの自動実行 | エージェント（LLM） |
| **MCP Inspector** | 開発中のデバッグ・テスト | 開発者 |
| **コーディング IDE** | 開発中にIDEからツールを利用 | 開発者 |

---

## 1. MCP Inspector（インスペクター）

MCPサーバーのための**開発者向けデバッグ・テストツール**です。いわば「MCPサーバー版 Postman」。

- WebブラウザベースのUIでMCPサーバーに接続
- ツール一覧の確認・手動実行・レスポンス確認が可能
- 公式ツール: https://github.com/modelcontextprotocol/inspector

### 起動方法

```bash
npx @modelcontextprotocol/inspector
```

これだけでブラウザが開き、以下ができます：

- MCPサーバーへの接続（stdio / Streamable HTTP）
- ツール一覧の表示（名前・説明・パラメータスキーマ）
- ツールの手動実行とレスポンス確認
- リソース・プロンプトの確認
- 通知ストリームの監視

### ローカルのMCPサーバーをテストする例

```bash
# stdio 接続（ローカルのPython MCPサーバー）
npx @modelcontextprotocol/inspector python my_mcp_server.py

# Streamable HTTP 接続（起動済みのサーバー）
npx @modelcontextprotocol/inspector --url http://localhost:8000/mcp
```

### AgentCore Gateway に接続する場合

Inspector の UI で Streamable HTTP を選択し：
- URL: `https://your-gateway-endpoint.amazonaws.com/mcp`
- ヘッダー: `Authorization: Bearer <your-jwt-token>`

を入力して Connect すると、Gateway に登録された全ツールが一覧表示されます。

### Inspector でできること

| 機能 | 説明 |
|---|---|
| ツール一覧 | 名前・説明・入力スキーマを表示 |
| ツール実行 | パラメータを入力して手動実行、結果を確認 |
| リソース確認 | MCPサーバーが公開するリソースを表示 |
| プロンプト確認 | サーバー定義のプロンプトテンプレートを表示 |
| 通知監視 | サーバーからの通知をリアルタイム表示 |

---

## 2. コーディング IDE

Kiro、VS Code (+ Copilot/GitHub Copilot)、Cursor、Windsurf などのIDEからMCPサーバーを利用する方法です。IDEのAIエージェントがツールとして認識し、コーディング中に自動的に利用できます。

### Kiro の場合

`.kiro/settings/mcp.json` に設定：

```json
{
  "mcpServers": {
    "my-gateway": {
      "command": "npx",
      "args": ["mcp-remote", "https://your-gateway-endpoint.amazonaws.com/mcp"],
      "env": {
        "MCP_HEADERS": "Authorization: Bearer <token>"
      }
    }
  }
}
```

ローカルのMCPサーバーの場合：

```json
{
  "mcpServers": {
    "my-local-server": {
      "command": "python",
      "args": ["my_mcp_server.py"],
      "env": {}
    }
  }
}
```

### VS Code の場合

`.vscode/mcp.json` に同様の設定を書きます：

```json
{
  "mcpServers": {
    "my-server": {
      "command": "python",
      "args": ["my_mcp_server.py"]
    }
  }
}
```

### IDE での利用の流れ

1. 設定ファイルにMCPサーバーを登録
2. IDE起動時に自動接続
3. AIエージェントがツール一覧を取得
4. ユーザーのリクエストに応じてエージェントがツールを選択・実行

---

## 3. エージェントフレームワーク

Strands Agents、LangChain、LangGraph 等からプログラムで `tools/list` や `tools/call` を呼ぶ方法。プロダクション環境で使用します。

### Strands での例

```python
from strands import Agent
from strands.tools.mcp.mcp_client import MCPClient
from mcp.client.streamable_http import streamablehttp_client

mcp_client = MCPClient(lambda: streamablehttp_client(
    "https://your-gateway-endpoint.amazonaws.com/mcp",
    headers={"Authorization": f"Bearer {token}"}
))

with mcp_client:
    tools = mcp_client.list_tools_sync()
    print(f"利用可能なツール: {[t.tool_name for t in tools]}")

    agent = Agent(tools=tools)
    response = agent("天気を教えて")
```

### MCP Client (Python SDK) での例

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
import asyncio

async def list_and_call():
    async with streamablehttp_client(
        url="https://your-gateway-endpoint.amazonaws.com/mcp",
        headers={"Authorization": f"Bearer {token}"}
    ) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            # ツール一覧
            tools = await session.list_tools()
            for tool in tools.tools:
                print(f"{tool.name}: {tool.description}")

            # ツール実行
            result = await session.call_tool(
                name="getCurrentWeather",
                arguments={"location": "Tokyo"}
            )
            print(result)

asyncio.run(list_and_call())
```

### LangGraph での例

```python
import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_aws import ChatBedrock

mcp_client = MultiServerMCPClient({
    "gateway": {
        "transport": "streamable_http",
        "url": "https://your-gateway-endpoint.amazonaws.com/mcp",
        "headers": {"Authorization": f"Bearer {token}"},
    }
})

tools = asyncio.run(mcp_client.get_tools())
print(f"ツール数: {len(tools)}")

model = ChatBedrock(model_id="anthropic.claude-sonnet-4-20250514-v1:0", region_name="us-west-2")
agent = create_react_agent(model, tools)

response = asyncio.run(agent.ainvoke({"messages": "東京の天気を教えて"}))
```

---

## 使い分けガイド

```
開発フェーズ:
  MCPサーバー作成 → Inspector でテスト → IDE で統合確認

本番フェーズ:
  エージェントフレームワーク で自動実行
```

| フェーズ | ツール | やること |
|---|---|---|
| サーバー開発中 | **MCP Inspector** | ツールが正しく公開されているか確認 |
| 統合テスト | **IDE** | AIエージェントが正しくツールを選択するか確認 |
| プロダクション | **フレームワーク** | エージェントが自律的にツールを検索・実行 |

---

## 参考リンク

- [MCP Inspector (GitHub)](https://github.com/modelcontextprotocol/inspector)
- [MCP Debugging Guide](https://modelcontextprotocol.io/docs/tools/debugging)
- [Kiro MCP設定ドキュメント](https://kiro.dev)
