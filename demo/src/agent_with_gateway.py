"""Phase 4: Secretary Agent - AgentCore Gateway 版

AgentCore 研修 Module 04 (Tools & Gateway) デモ用。
AgentCore Gateway 経由で Lambda ツールに接続し、
エージェントがツールを自律的に使い分ける様子をデモします。

実行方法:
    python -u agent_with_gateway.py

前提条件:
    - AgentCore Gateway が作成済み
    - Lambda ターゲット（schedule / weather）が追加済み
    - 環境変数 GATEWAY_URL が設定済み
    - pip install mcp-proxy-for-aws

デモの流れ:
    1. 「今日のスケジュールを教えて」 → Gateway 経由で schedule Lambda
    2. 「東京の天気は？」 → Gateway 経由で weather Lambda
    3. 「利用可能なツールを教えて」 → tools/list で自動検出

環境変数:
    GATEWAY_URL: AgentCore Gateway の MCP エンドポイント URL
    AWS_REGION: リージョン (default: us-east-1)
    AWS_PROFILE: AWS プロファイル名
"""

import os
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client

from config import get_system_prompt, get_model_id, REGION

# ========================================
# 設定
# ========================================
GATEWAY_URL = os.environ.get("GATEWAY_URL", "")

# ========================================
# 設定取得（SSM Parameter Store）
# ========================================
print("📌 設定を読み込み中...")
system_prompt = get_system_prompt()
model_id = get_model_id()
print(f"   Model: {model_id}")
print(f"   Gateway: {GATEWAY_URL or '未設定'}")

# ========================================
# システムプロンプトにツール利用指示を追加
# ========================================
TOOLS_INSTRUCTION = """

ツールを積極的に活用して、正確な情報に基づいて回答してください。
利用可能なツールは AgentCore Gateway 経由で自動検出されます。
複数のツールを組み合わせて判断が必要な場合は、順番に呼び出して総合的に回答してください。
"""

full_system_prompt = system_prompt + TOOLS_INSTRUCTION

# ========================================
# モデル設定
# ========================================
model = BedrockModel(
    model_id=model_id,
    region_name=REGION,
)


def get_gateway_client() -> MCPClient:
    """AgentCore Gateway に接続する MCP クライアントを取得する。

    SigV4 認証で Gateway に接続し、ツールを自動検出する。
    """
    return MCPClient(lambda: aws_iam_streamablehttp_client(
        endpoint=GATEWAY_URL,
        aws_region=REGION,
        aws_service="bedrock-agentcore",
    ))


def main():
    """対話ループ"""
    if not GATEWAY_URL:
        print()
        print("❌ GATEWAY_URL が設定されていません。")
        print("   export GATEWAY_URL='https://<your-gateway-id>.bedrock-agentcore.<region>.amazonaws.com/mcp'")
        print()
        return

    print()
    print("=" * 60)
    print("🤖 Secretary Agent - Phase 4 (AgentCore Gateway)")
    print("   AgentCore 研修デモ: Gateway 経由ツール利用版")
    print("   終了するには 'quit' または 'exit' と入力")
    print("=" * 60)
    print()
    print("📡 Gateway に接続中...")

    gateway = get_gateway_client()

    with gateway:
        # ツール自動検出
        tools = gateway.list_tools_sync()
        print(f"   ✅ 接続成功！ {len(tools)} 個のツールを検出:")
        for tool in tools:
            print(f"      - {tool.name}: {tool.description[:50]}...")
        print()
        print("💡 試してみてください:")
        print("   - 「今日のスケジュールを教えて」")
        print("   - 「東京の天気は？」")
        print("   - 「来週の予定を教えて」")
        print()

        # エージェント作成（Gateway から取得したツール付き）
        agent = Agent(
            model=model,
            system_prompt=full_system_prompt,
            tools=tools,
        )

        while True:
            try:
                user_input = input("👤 You: ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ("quit", "exit", "q"):
                    print("\n👋 お疲れ様でした！")
                    break

                print("\n🤖 Secretary: ", end="")
                result = agent(user_input)
                print("\n")

            except KeyboardInterrupt:
                print("\n\n👋 お疲れ様でした！")
                break


if __name__ == "__main__":
    main()
