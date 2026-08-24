# M02: AgentCore Runtime の非同期ジョブと長時間実行ジョブ

## 概要

AgentCore Runtime では、レポート生成やデータ分析など**時間のかかる処理**をバックグラウンドで実行し、
クライアントには即時応答を返すパターンが用意されています。

### アーキテクチャ

```
Client → Agent (即時応答: "タスク開始しました")
                ↓
         Background Thread → 重い処理実行
                ↓
         app.complete_async_task() → Runtime に完了通知
```

---

## 1. AgentCore SDK でエージェントを構築する基本形

まず、AgentCore Runtime 上でエージェントを動かす基本構造です。

```python
# SDK でエージェントを構築する
from bedrock_agentcore.runtime import BedrockAgentCoreApp

# 使用例
app = BedrockAgentCoreApp()

@app.entrypoint
def my_agent(request):
    # エージェントロジックを実装する
    return response

app.run()
```

### 解説

| 要素 | 役割 |
|------|------|
| `BedrockAgentCoreApp` | AgentCore Runtime とやり取りするアプリケーションオブジェクト。ヘルスチェック(`/ping`)やエージェント呼び出し(`/invocations`)のエンドポイントを自動で提供する |
| `@app.entrypoint` | このデコレータで登録した関数が、`/invocations` で呼ばれるエントリーポイントになる |
| `app.run()` | HTTPサーバーを起動し、Runtime からのリクエストを待ち受ける |

`my_agent` の中身に **Strands Agents SDK** や LangChain などでエージェントロジックを実装します。

---

## 2. 非同期タスク（長時間実行ジョブ）の実装

時間のかかる処理をバックグラウンドで実行するツールの定義です。

```python
@tool
def start_background_task(duration: int = 5) -> str:

    # 非同期タスクの追跡を開始する
    task_id = app.add_async_task("report_generation", {"duration": duration})

    # バックグラウンドスレッドでタスクを実行する
    def background_work():
        # ワークロジックの例
        app.complete_async_task(task_id)  # 完了としてマークする

    threading.Thread(target=background_work, daemon=True).start()

    return f"Started background task (ID: {task_id}) for {duration} seconds. Agent status is now BUSY."
```

### 解説

#### `@tool` デコレータ
- Strands Agents SDK のデコレータ
- この関数を「エージェントが呼べるツール」として登録する
- LLM がユーザーの意図に応じて自動的にこのツールを呼ぶか判断する

#### `app.add_async_task("report_generation", {"duration": duration})`
- AgentCore Runtime に「非同期タスクを開始する」ことを登録する
- 第1引数: タスクの種類名（任意の文字列）
- 第2引数: メタデータ（辞書形式で任意の情報を渡せる）
- 戻り値: `task_id`（タスクを一意に識別するID）
- Runtime 側でタスクのステータス（進行中/完了）を追跡管理してくれる

#### `def background_work():` — バックグラウンド処理
- この内部関数の中に**実際の重い処理**を書く
- 例: S3からデータ取得、PDF生成、外部API呼び出し、データ集計など

```python
def background_work():
    # 実際の処理例:
    data = fetch_data_from_s3(bucket, key)
    report = generate_report(data)
    upload_to_s3(report, output_bucket, output_key)
    
    # 全て終わったら完了を通知
    app.complete_async_task(task_id)
```

#### `app.complete_async_task(task_id)`
- Runtime に「このタスクは完了した」と通知する
- これにより Runtime 側のタスクステータスが更新される
- クライアントは後から task_id でステータスを問い合わせ可能

#### `threading.Thread(target=background_work, daemon=True).start()`
- Python 標準の `threading` でバックグラウンドスレッドを起動
- `daemon=True`: メインプロセスが終了すると自動的にスレッドも終了する
- `.start()` で即座にスレッドを開始し、**呼び出し元はブロックされない**

#### `return "Started background task ..."`
- ツールの戻り値として即座にクライアントへ返される
- 実際の処理完了を待たずに応答するのがポイント

---

## 3. 全体を組み合わせた完全な実装例

上記を組み合わせた実用的なサンプルコードです。

```python
"""AgentCore Runtime 非同期ジョブ サンプル"""

import os
import time
import threading

from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp

# ========================================
# 設定
# ========================================
REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL_ID = os.environ.get("MODEL_ID", "us.amazon.nova-pro-v1:0")

SYSTEM_PROMPT = """あなたは優秀なアシスタントです。
レポート生成など時間のかかる処理はバックグラウンドで実行し、即座に応答します。
"""

# ========================================
# AgentCore Runtime アプリケーション
# ========================================
app = BedrockAgentCoreApp()


# ========================================
# 非同期タスク用ツール
# ========================================
@tool
def start_report_generation(duration: int = 5) -> str:
    """レポートをバックグラウンドで生成する。

    Args:
        duration: レポート生成にかかる想定秒数
    """
    # Runtime にタスク登録
    task_id = app.add_async_task("report_generation", {"duration": duration})

    def background_work():
        try:
            # ===== 実際の処理をここに書く =====
            print(f"[Task {task_id}] レポート生成開始...")
            time.sleep(duration)  # ← 本番ではDB集計やPDF生成など
            print(f"[Task {task_id}] レポート生成完了!")
            # ==================================

            app.complete_async_task(task_id)  # 完了通知

        except Exception as e:
            print(f"[Task {task_id}] エラー: {e}")
            app.complete_async_task(task_id)

    threading.Thread(target=background_work, daemon=True).start()

    return f"Started background task (ID: {task_id}) for {duration} seconds. Agent status is now BUSY."


# ========================================
# エントリーポイント
# ========================================
@app.entrypoint
async def invoke(payload, context):
    """POST /invocations で呼ばれるエージェント処理"""
    user_input = payload.get("prompt", "")

    model = BedrockModel(model_id=MODEL_ID, region_name=REGION)

    agent = Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[start_report_generation],  # 非同期タスクツールを登録
    )

    response = agent(user_input)
    return response.message["content"][0]["text"]


# ========================================
# 起動
# ========================================
if __name__ == "__main__":
    app.run()
```

---

## 4. デプロイ手順（スターターツールキットなし）

スライド「スターターツールキットを使用せずに始める」の手順に対応:

| # | ステップ | 内容 |
|---|----------|------|
| 1 | Observability 有効化 | Dockerfile で `opentelemetry-instrument` を使って起動 |
| 2 | uv インストール | `pip install uv` で高速パッケージマネージャを導入 |
| 3 | エージェントコード定義 | 上記コード。`/invocations`(POST) と `/ping`(GET) を `app.run()` が自動提供 |
| 4 | ローカルテスト | `python agent_async_tasks.py` で起動し、curl で `/invocations` を叩く |
| 5 | Dockerfile 作成 | 下記参照 |
| 6 | ECR にデプロイ | `docker build` → `docker push` |
| 7 | Runtime デプロイ | コンソールで Runtime を作成し、ECR イメージを指定 |

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 8080

# OTel 自動計装で起動（Observability 有効化）
CMD ["opentelemetry-instrument", "python", "agent_async_tasks.py"]
```

### requirements.txt

```
strands-agents>=0.1.0
bedrock-agentcore[strands-agents]>=0.1.0
aws-opentelemetry-distro>=0.10.0
boto3>=1.35.0
```

---

## 5. まとめ

- `BedrockAgentCoreApp` がインフラ層（ヘルスチェック、エンドポイント、タスク管理）を担当
- `@app.entrypoint` の中身が実際のエージェントロジック（Strands で実装）
- `app.add_async_task()` / `app.complete_async_task()` で長時間タスクを非同期管理
- クライアントは即時応答を受け取り、タスク完了は後から確認できる
