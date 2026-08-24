"""Module 02: BedrockAgentCoreApp を使った推奨パターン

bedrock-agentcore パッケージの BedrockAgentCoreApp を使うと、
/invocations と /ping のルーティングが自動的に設定されます。

内部的には以下と同等の処理が行われます:
  - GET /ping → 200 OK を返す
  - POST /invocations → @app.entrypoint で定義した関数を実行

実行方法（ローカルテスト）:
    python agent_endpoint_bedrock_agentcore.py

前提条件:
    - pip install bedrock-agentcore[strands-agents] strands-agents boto3
"""

import os
from strands import Agent
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp

# ========================================
# 設定
# ========================================
MODEL_ID = os.environ.get("MODEL_ID", "us.amazon.nova-pro-v1:0")
REGION = os.environ.get("AWS_REGION", "us-east-1")
SYSTEM_PROMPT = """あなたは優秀な秘書エージェントです。
簡潔で正確な情報を提供し、日本語で応答してください。"""

# ========================================
# BedrockAgentCoreApp の初期化
# ========================================
# これだけで /ping と /invocations が自動的に構成される
app = BedrockAgentCoreApp()


# ========================================
# エントリポイント定義
# ========================================
@app.entrypoint
async def invoke(payload, context):
    """エージェントのメインロジック。

    BedrockAgentCoreApp が POST /invocations を受けると、
    この関数が自動的に呼び出されます。

    Args:
        payload: リクエストボディの JSON（dict）
            - prompt: ユーザー入力テキスト
            - actor_id: ユーザー識別子（オプション）
        context: AgentCore が提供するコンテキスト情報
            - session_id: セッション識別子
            - その他のランタイム情報

    Returns:
        str: エージェントの応答テキスト
    """
    user_input = payload.get("prompt", "")
    # session_id = context.session_id  # AgentCore が自動管理

    # モデル設定
    model = BedrockModel(model_id=MODEL_ID, region_name=REGION)

    # エージェント作成
    agent = Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
    )

    # 実行して応答を返す
    result = agent(user_input)
    return result.message["content"][0]["text"]


# ========================================
# メイン
# ========================================
if __name__ == "__main__":
    # BedrockAgentCoreApp.run() で起動
    # 内部的に uvicorn が port 8080 で起動する
    app.run()
