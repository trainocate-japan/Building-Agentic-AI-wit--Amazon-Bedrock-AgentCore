# AgentCore Gateway セマンティック検索

## 概要

AgentCore Gateway のセマンティック検索は、ツール数が多い（300以上など）場合に、全ツール一覧を返す代わりに**自然言語クエリで関連ツールを絞り込む**機能です。

Gateway に `x_amz_bedrock_agentcore_search` という組み込みツールが追加され、エージェントはキーワード一致ではなく**意味的な類似度**で適切なツールを発見できます。

### 検索あり vs なし

| | 検索なし (`tools/list`) | 検索あり (`x_amz_bedrock_agentcore_search`) |
|---|---|---|
| 動作 | 全ツールを返す | 自然言語クエリに関連する上位ツールを返す |
| 300+ツール | LLMのコンテキスト超過リスク | 上位10件程度に絞られる |
| 精度 | LLMが全ツールから選択（ノイズ大） | 意味的に関連するツールのみ提示 |
| レイテンシ | 全件転送のコスト | 検索+少数件転送で高速 |

---

## Step 1: Gateway 作成時にセマンティック検索を有効化

### Boto3

```python
import boto3

agentcore_client = boto3.client('bedrock-agentcore-control')

response = agentcore_client.create_gateway(
    name="my-gateway",
    roleArn="arn:aws:iam::123456789012:role/my-gateway-service-role",
    protocolType="MCP",
    authorizerType="CUSTOM_JWT",
    authorizerConfiguration={
        "customJWTAuthorizer": {
            "discoveryUrl": "https://cognito-idp.us-west-2.amazonaws.com/your-user-pool/.well-known/openid-configuration",
            "allowedClients": ["your-client-id"]
        }
    },
    protocolConfiguration={
        "mcp": {
            "searchType": "SEMANTIC"  # ← これがキー
        }
    }
)

gateway_url = response["gatewayUrl"]
print(f"Gateway URL: {gateway_url}")
```

### AWS CLI

```bash
aws bedrock-agentcore-control create-gateway \
    --name my-gateway \
    --role-arn arn:aws:iam::123456789012:role/my-gateway-service-role \
    --protocol-type MCP \
    --authorizer-type CUSTOM_JWT \
    --authorizer-configuration '{
        "customJWTAuthorizer": {
            "discoveryUrl": "https://cognito-idp.us-west-2.amazonaws.com/some-user-pool/.well-known/openid-configuration",
            "allowedClients": ["clientId"]
        }
    }' \
    --protocol-configuration '{
        "mcp": {
            "searchType": "SEMANTIC"
        }
    }'
```

### AgentCore CLI（デフォルトで有効）

```bash
agentcore add gateway --name my-gateway
agentcore deploy
# セマンティック検索は AgentCore CLI ではデフォルト有効
# 無効にしたい場合は --no-semantic-search を付ける
```

---

## Step 2: ツール検索を実行

### Python (requests)

```python
import requests
import json

def search_tools(gateway_url, access_token, query):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
        "MCP-Protocol-Version": "2025-11-25"
    }

    payload = {
        "jsonrpc": "2.0",
        "id": "search-tools-request",
        "method": "tools/call",
        "params": {
            "name": "x_amz_bedrock_agentcore_search",
            "arguments": {
                "query": query
            }
        }
    }

    response = requests.post(f"{gateway_url}/mcp", headers=headers, json=payload)
    return response.json()

# 使用例
results = search_tools(
    gateway_url="https://your-gateway-endpoint.amazonaws.com",
    access_token="your-jwt-token",
    query="ソーシャルメディアへの投稿を作成する"
)

tools = results["result"]["structuredContent"]["tools"]
print(f"見つかったツール数: {len(tools)}")
for tool in tools:
    print(f"  - {tool['name']}: {tool.get('description', '')}")
```

### MCP Client (Python SDK)

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
import asyncio

async def search_tools_mcp(gateway_url, token, query):
    headers = {"Authorization": f"Bearer {token}"}

    async with streamablehttp_client(
        url=f"{gateway_url}/mcp",
        headers=headers,
    ) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            search_result = await session.call_tool(
                name="x_amz_bedrock_agentcore_search",
                arguments={"query": query}
            )
            print(f"検索結果: {search_result}")
            return search_result

asyncio.run(search_tools_mcp(
    "https://your-gateway-endpoint.amazonaws.com",
    "your-jwt-token",
    "ソーシャルメディアへの投稿を作成する"
))
```

### Strands MCP Client

```python
from strands.tools.mcp.mcp_client import MCPClient
from mcp.client.streamable_http import streamablehttp_client

def create_transport(mcp_url, access_token):
    return streamablehttp_client(mcp_url, headers={"Authorization": f"Bearer {access_token}"})

def search_with_gateway(mcp_url, access_token, query):
    mcp_client = MCPClient(lambda: create_transport(mcp_url, access_token))

    with mcp_client:
        result = mcp_client.call_tool_sync(
            tool_use_id="search-123",
            name="x_amz_bedrock_agentcore_search",
            arguments={"query": query}
        )
        print(result)
        return result

search_with_gateway(
    "https://your-gateway-endpoint.amazonaws.com/mcp",
    "your-jwt-token",
    "find order information"
)
```

---

## Step 3: 検索で見つけたツールを呼ぶ

検索結果にはツール名とスキーマが含まれるので、同じセッション・同じエンドポイントで `tools/call` するだけです。

### 通信フロー

```
エージェント                        AgentCore Gateway
    |                                     |
    |-- 1. tools/call (search) ---------->|  ← セマンティック検索
    |<-- 関連ツール一覧 ------------------|
    |                                     |
    |-- 2. tools/call (実際のツール) ----->|  ← 検索結果のツールを呼ぶ
    |<-- 実行結果 ------------------------|
```

### 完全な例: 検索 → 実行

```python
import requests
import json

GATEWAY_URL = "https://your-gateway-endpoint.amazonaws.com/mcp"
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {access_token}",
    "MCP-Protocol-Version": "2025-11-25"
}

# ===== Step 1: セマンティック検索 =====
search_payload = {
    "jsonrpc": "2.0",
    "id": "step1-search",
    "method": "tools/call",
    "params": {
        "name": "x_amz_bedrock_agentcore_search",
        "arguments": {
            "query": "ソーシャルメディアへの投稿を作成する"
        }
    }
}

search_response = requests.post(GATEWAY_URL, headers=HEADERS, json=search_payload)
search_results = search_response.json()

# 検索結果からツール情報を取得
tools = search_results["result"]["structuredContent"]["tools"]
print(f"見つかったツール: {[t['name'] for t in tools]}")
# => ['createSocialPost', 'scheduleSocialPost', ...]

# ===== Step 2: 見つかったツールを呼ぶ =====
call_payload = {
    "jsonrpc": "2.0",
    "id": "step2-call",
    "method": "tools/call",
    "params": {
        "name": "createSocialPost",  # ← 検索で見つけたツール名
        "arguments": {
            "content": "AgentCore Gatewayのセマンティック検索機能を試しています！",
            "platform": "twitter"
        }
    }
}

call_response = requests.post(GATEWAY_URL, headers=HEADERS, json=call_payload)
result = call_response.json()
print(json.dumps(result, indent=2))
```

### MCP Client での検索 → 実行

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
import asyncio
import json

async def search_and_call(gateway_url, token):
    headers = {"Authorization": f"Bearer {token}"}

    async with streamablehttp_client(
        url=gateway_url, headers=headers
    ) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            # Step 1: 検索
            search_result = await session.call_tool(
                name="x_amz_bedrock_agentcore_search",
                arguments={"query": "注文情報を検索する"}
            )

            # 検索結果からツール名を取得
            tools = json.loads(search_result.content[0].text)["tools"]
            tool_name = tools[0]["name"]  # 最も関連性の高いツール
            print(f"使用するツール: {tool_name}")

            # Step 2: そのツールを呼ぶ
            result = await session.call_tool(
                name=tool_name,
                arguments={"orderId": "ORD-12345"}
            )
            print(f"実行結果: {result}")

asyncio.run(search_and_call(
    "https://your-gateway-endpoint.amazonaws.com/mcp",
    "your-jwt-token"
))
```

### LLMエージェントが自動で検索 → 実行する場合

実際のエージェント運用では、LLMが自律的に検索と実行を行います：

```python
from strands import Agent
from strands.tools.mcp.mcp_client import MCPClient
from mcp.client.streamable_http import streamablehttp_client

# GatewayをMCPクライアントとして接続
mcp_client = MCPClient(lambda: streamablehttp_client(
    gateway_url, headers={"Authorization": f"Bearer {token}"}
))

with mcp_client:
    tools = mcp_client.list_tools_sync()
    # ↑ ここで x_amz_bedrock_agentcore_search ツールが見える

    agent = Agent(tools=tools)

    # エージェントに依頼すると：
    # 1. LLMが「検索ツール使おう」と判断して search を呼ぶ
    # 2. 結果を見て適切なツールを選んで呼ぶ
    response = agent("先週の注文一覧を見せて")
```

---

## OpenAPI に `x-amz-bedrock-agentcore-search` 拡張を追加

OpenAPIターゲットの各操作に自然言語の説明を追加すると、セマンティック検索の精度が向上します。

```json
{
  "openapi": "3.0.0",
  "info": {
    "title": "Social Media API",
    "version": "1.0.0"
  },
  "servers": [{"url": "https://api.example.com/v1"}],
  "paths": {
    "/posts": {
      "post": {
        "operationId": "createSocialPost",
        "summary": "Create a social media post",
        "description": "Creates a new post on social media platforms",
        "x-amz-bedrock-agentcore-search": "ソーシャルメディアへの新しい投稿を作成する。Twitter、Facebook、Instagramへの投稿に使用できる。",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "properties": {
                  "content": {"type": "string", "description": "投稿内容"},
                  "platform": {"type": "string", "enum": ["twitter", "facebook", "instagram"]},
                  "scheduled_at": {"type": "string", "format": "date-time"}
                },
                "required": ["content", "platform"]
              }
            }
          }
        },
        "responses": {
          "201": {"description": "投稿が作成されました"}
        }
      }
    },
    "/posts/{postId}/analytics": {
      "get": {
        "operationId": "getPostAnalytics",
        "summary": "Get post analytics",
        "x-amz-bedrock-agentcore-search": "投稿のパフォーマンスを分析する。いいね数、リーチ、エンゲージメント率などの指標を取得する。",
        "parameters": [
          {"name": "postId", "in": "path", "required": true, "schema": {"type": "string"}}
        ],
        "responses": {
          "200": {"description": "分析結果"}
        }
      }
    }
  }
}
```

**ポイント**: `x-amz-bedrock-agentcore-search` フィールドには、操作の技術的な名称だけでなく、**ユーザーが会話的に表現しそうな説明文**を書きます。これにより「SNSに投稿したい」→ `createSocialPost` のようなマッチが可能になります。

---

## 検索の仕組み（内部動作）

1. ターゲット追加/同期時に、各ツールの `name`, `description`, `inputSchema` から**エンベディング（ベクトル）**を生成
2. 検索クエリが来ると、クエリのエンベディングとツールのエンベディングの**コサイン類似度**で関連性をランキング
3. 上位の関連ツール（名前・説明・スキーマ含む）を返却

リアルタイムにMCPサーバーと通信するのではなく、同期済みのインデックスに対して検索するため高速です。

---

## ツール同期 (SynchronizeGatewayTargets)

MCPサーバー側でツール定義が更新された場合、インデックスを再同期する必要があります：

```python
agentcore_client.synchronize_gateway_targets(
    gatewayIdentifier="your-gateway-id"
)
```

同期フロー：
1. Gateway が MCPサーバーに `initialize` → `tools/list` を呼び出し
2. ツール定義を取得（100件ずつページネーション）
3. ツール名にターゲット固有プレフィックスを付与
4. エンベディングを再生成してインデックス更新

---

## まとめ

| ポイント | 内容 |
|---|---|
| 有効化 | `protocolConfiguration.mcp.searchType = "SEMANTIC"` |
| 検索ツール名 | `x_amz_bedrock_agentcore_search` |
| 検索方法 | `tools/call` で query 引数に自然言語を渡す |
| 使用方法 | 検索結果のツール名で再度 `tools/call` |
| 精度向上 | OpenAPI に `x-amz-bedrock-agentcore-search` 拡張を追加 |
| 同期 | `SynchronizeGatewayTargets` API でインデックス更新 |

---

## 参考リンク

- [セマンティック検索の使い方](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-using-mcp-semantic-search.html)
- [Gateway作成時のセマンティック検索設定](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-create-api.html)
- [AWSブログ: Transform your MCP architecture](https://aws.amazon.com/blogs/machine-learning/transform-your-mcp-architecture-unite-mcp-servers-through-agentcore-gateway/)
- [AWSブログ: Introducing AgentCore Gateway](https://aws.amazon.com/blogs/machine-learning/introducing-amazon-bedrock-agentcore-gateway-transforming-enterprise-ai-agent-tool-development/)
