"""Secretary Agent - AgentCore Runtime デプロイ版

BedrockAgentCoreApp を使った推奨パターン。
ECR にプッシュし、コンソールから Runtime を作成してデプロイする。

機能:
    - SSM Parameter Store からプロンプト/モデルを取得（毎回最新）
    - AgentCore Gateway 経由でツール利用
    - AgentCore Memory で短期メモリ保存 + 長期メモリ自動取得

環境変数:
    GATEWAY_URL: AgentCore Gateway の MCP エンドポイント URL
    AGENTCORE_MEMORY_ID: AgentCore Memory の ID
    MEMORY_PREFERENCE_STRATEGY_ID: USER_PREFERENCE 戦略 ID
    MEMORY_SEMANTIC_STRATEGY_ID: SEMANTIC 戦略 ID
    AWS_REGION: リージョン (default: us-east-1)
    PARAMETER_PREFIX: SSM パラメータのプレフィックス
"""

import os
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.memory.integrations.strands.config import (
    AgentCoreMemoryConfig,
    RetrievalConfig,
)
from bedrock_agentcore.memory.integrations.strands.session_manager import (
    AgentCoreMemorySessionManager,
)

from config import get_system_prompt, get_model_id, REGION

GATEWAY_URL = os.environ.get("GATEWAY_URL", "")
MEMORY_ID = os.environ.get("AGENTCORE_MEMORY_ID", "")
PREFERENCE_STRATEGY_ID = os.environ.get("MEMORY_PREFERENCE_STRATEGY_ID", "")
SEMANTIC_STRATEGY_ID = os.environ.get("MEMORY_SEMANTIC_STRATEGY_ID", "")

app = BedrockAgentCoreApp()


@app.entrypoint
async def invoke(payload, context):
    """エージェントを呼び出す。invoke のたびに設定を取得する。"""
    user_input = payload.get("prompt", "")
    actor_id = payload.get("actor_id", "default")
    session_id = context.session_id or "default"

    # 毎回 Parameter Store から最新値を取得
    system_prompt = get_system_prompt()
    model_id = get_model_id()

    model = BedrockModel(model_id=model_id, region_name=REGION)

    # Memory 設定（長期メモリの自動取得を有効化）
    session_manager = None
    if MEMORY_ID and (PREFERENCE_STRATEGY_ID or SEMANTIC_STRATEGY_ID):
        retrieval_config = {}
        if PREFERENCE_STRATEGY_ID:
            ns_pref = f"secretary/instructor/{actor_id}/preferences"
            retrieval_config[ns_pref] = RetrievalConfig()
        if SEMANTIC_STRATEGY_ID:
            ns_sem = f"secretary/instructor/{actor_id}/facts"
            retrieval_config[ns_sem] = RetrievalConfig()

        memory_config = AgentCoreMemoryConfig(
            memory_id=MEMORY_ID,
            session_id=session_id,
            actor_id=actor_id,
            retrieval_config=retrieval_config,
        )
        session_manager = AgentCoreMemorySessionManager(
            agentcore_memory_config=memory_config
        )
    else:
        print("Memory disabled: AGENTCORE_MEMORY_ID or strategy IDs not set")

    # Gateway 経由でツール取得
    gateway = MCPClient(lambda: aws_iam_streamablehttp_client(
        endpoint=GATEWAY_URL,
        aws_region=REGION,
        aws_service="bedrock-agentcore",
    ))

    with gateway:
        tools = gateway.list_tools_sync()
        agent = Agent(
            model=model,
            system_prompt=system_prompt,
            tools=tools,
            session_manager=session_manager,
        )
        response = agent(user_input)

    return response.message["content"][0]["text"]


if __name__ == "__main__":
    app.run()
