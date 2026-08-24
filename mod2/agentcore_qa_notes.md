# M02: セッション中の Q&A メモ

このセッションで確認した内容をまとめたノートです。

---

## Q1: `def background_work():` の下に実際の処理を書くのか？

### 回答: はい

`background_work()` の中に実際の重い処理を書きます。
スライドでは `# ワークロジックの例` とコメントだけですが、実際にはこうなります:

```python
def background_work():
    # ===== 実際の処理をここに書く =====
    data = fetch_data_from_s3(bucket, key)   # データ取得
    report = generate_report(data)            # レポート生成
    upload_to_s3(report, output_bucket, key)  # 結果保存
    # ==================================

    app.complete_async_task(task_id)  # 全部終わったら完了マーク
```

### ポイント

- 実際の処理を `complete_async_task` の**前**に書く
- 処理が全部終わってから `complete_async_task` を呼ぶ
- 本番ではエラーハンドリング（`try/except`）も入れるべき

---

## Q2: `app` は何か？

### 回答: AgentCore Runtime のアプリケーションインスタンス

```python
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()
```

### `app` が提供する役割

| 役割 | 説明 |
|------|------|
| エージェントのライフサイクル管理 | Runtime 上でのエージェントの起動・停止 |
| 非同期タスク管理 | `add_async_task()` / `complete_async_task()` でタスクの状態追跡 |
| ヘルスチェック応答 | Runtime からの死活監視（`GET /ping`）に応答 |
| ステータス管理 | エージェントが BUSY / READY かを Runtime に通知 |
| エンドポイント提供 | `app.run()` で `/invocations`(POST) と `/ping`(GET) を自動起動 |

### 関係図

```
AgentCore Runtime ←→ app (BedrockAgentCoreApp)
                         ├── /invocations  → @app.entrypoint の関数
                         └── /ping         → ヘルスチェック（自動）
```

`app` は AgentCore Runtime と通信するためのインターフェースオブジェクト。

---

## Q3: エージェントロジックは Strands などでの実装か？

### 回答: はい

`@app.entrypoint` で登録した関数の**中身**がエージェントロジックで、
ここに Strands Agents SDK などを使った実装を書きます。

### 構造の整理

```python
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

@app.entrypoint
def my_agent(request):
    # ← ここにエージェントロジック（Strands等）を実装
    return response

app.run()
```

### 役割分担

| レイヤー | 担当 | 例 |
|----------|------|-----|
| **AgentCore Runtime SDK** (`BedrockAgentCoreApp`) | ホスティング・ライフサイクル・非同期タスク管理 | `app.run()`, `app.add_async_task()` |
| **エージェントロジック** (`my_agent` の中身) | LLM呼び出し・ツール使用・推論ループ | Strands Agents, LangChain, 独自実装 |

### Strands を使う場合の例

```python
@app.entrypoint
async def invoke(payload, context):
    from strands import Agent
    from strands.models import BedrockModel

    model = BedrockModel(model_id="us.anthropic.claude-sonnet-4-20250514", region_name="us-east-1")

    agent = Agent(
        model=model,
        system_prompt="あなたは優秀なアシスタントです。",
        tools=[my_tool_1, my_tool_2],
    )

    response = agent(payload.get("prompt", ""))
    return response.message["content"][0]["text"]
```

### フレームワーク非依存

AgentCore Runtime はフレームワークに依存しないので、以下のどれでも使えます:

- **Strands Agents SDK** — AWS公式。最も統合が深い（推奨）
- **LangChain / LangGraph** — エコシステムが豊富
- **独自実装** — boto3 で直接 Bedrock API を呼ぶ

ただし AWS 公式としては Strands が最も統合が深い選択肢です。
