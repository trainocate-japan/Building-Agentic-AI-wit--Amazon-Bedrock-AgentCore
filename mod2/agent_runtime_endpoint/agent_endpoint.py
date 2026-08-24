"""Module 02: AgentCore Runtime 用エージェントエンドポイント

AgentCore Runtime にデプロイするためのエージェントコードです。
スターターツールキットを使用せずに、FastAPI で以下の2つのエンドポイントを定義します:

  - POST /invocations : エージェントインタラクション用エンドポイント
  - GET  /ping        : ヘルスチェック用エンドポイント

AgentCore Runtime はコンテナに対してこの2つのエンドポイントを呼び出します:
  1. /ping でコンテナの起動確認（ヘルスチェック）
  2. /invocations でユーザーからのリクエストを処理

実行方法（ローカルテスト）:
    uvicorn agent_endpoint:app --host 0.0.0.0 --port 8080

前提条件:
    - AWS CLI が設定済み
    - Bedrock モデルアクセスが有効
    - pip install fastapi uvicorn strands-agents boto3
"""

import json
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from strands import Agent
from strands.models import BedrockModel

# ========================================
# FastAPI アプリケーション
# ========================================
app = FastAPI(
    title="Secretary Agent - AgentCore Runtime",
    description="AgentCore Runtime 用エージェントエンドポイント",
)

# ========================================
# 設定
# ========================================
MODEL_ID = "us.amazon.nova-pro-v1:0"
REGION = "us-east-1"
SYSTEM_PROMPT = """あなたは優秀な秘書エージェントです。
簡潔で正確な情報を提供し、日本語で応答してください。"""


# ========================================
# GET /ping - ヘルスチェック
# ========================================
@app.get("/ping")
async def ping():
    """ヘルスチェック用エンドポイント。

    AgentCore Runtime はこのエンドポイントを定期的に呼び出し、
    コンテナが正常に稼働していることを確認します。

    Returns:
        200 OK を返すだけでよい
    """
    return PlainTextResponse("OK", status_code=200)


# ========================================
# POST /invocations - エージェント呼び出し
# ========================================
@app.post("/invocations")
async def invocations(request: Request):
    """エージェントインタラクション用エンドポイント。

    AgentCore Runtime がユーザーリクエストをこのエンドポイントに転送します。
    リクエストボディにはエージェント定義（プロンプト等）が含まれます。

    Request Body (JSON):
        {
            "prompt": "ユーザーからの入力テキスト",
            "session_id": "セッション識別子（オプション）"
        }

    Returns:
        エージェントの応答テキスト
    """
    try:
        # リクエストボディを解析
        body = await request.json()
        user_input = body.get("prompt", "")

        if not user_input:
            return JSONResponse(
                content={"error": "prompt is required"},
                status_code=400,
            )

        # Bedrock モデルの設定
        model = BedrockModel(
            model_id=MODEL_ID,
            region_name=REGION,
        )

        # エージェントの作成と実行
        agent = Agent(
            model=model,
            system_prompt=SYSTEM_PROMPT,
        )

        # エージェントを呼び出し
        result = agent(user_input)

        # レスポンスのテキストを抽出
        response_text = result.message["content"][0]["text"]

        return PlainTextResponse(response_text, status_code=200)

    except Exception as e:
        return JSONResponse(
            content={"error": str(e)},
            status_code=500,
        )


# ========================================
# メイン（ローカルテスト用）
# ========================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
