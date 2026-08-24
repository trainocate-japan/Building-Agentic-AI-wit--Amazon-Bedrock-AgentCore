"""Phase 1: Secretary Agent - ローカル実行版

AgentCore 研修 Module 01 (Foundations) デモ用。
Strands Agent SDK の基本的な使い方を示します。

実行方法:
    python -u agent.py

前提条件:
    - AWS CLI が設定済み (aws configure)
    - Bedrock モデルアクセスが有効 (Amazon Nova Pro)
    - SSM Parameter Store にシステムプロンプトを登録済み
    - pip install strands-agents boto3
"""

from strands import Agent
from strands.models import BedrockModel

from config import get_system_prompt, get_model_id, REGION

# ========================================
# 設定取得（SSM Parameter Store）
# ========================================
print("📌 設定を読み込み中...")
system_prompt = get_system_prompt()
model_id = get_model_id()
print(f"   Model: {model_id}")
print(f"   Prompt: {system_prompt[:40]}...")

# ========================================
# モデル設定
# ========================================
model = BedrockModel(
    model_id=model_id,
    region_name=REGION,
)

# ========================================
# エージェント作成（ツールなし - 基本版）
# ========================================
agent = Agent(
    model=model,
    system_prompt=system_prompt,
)


def main():
    """対話ループ"""
    print()
    print("=" * 60)
    print("🤖 Secretary Agent - Phase 1 (Basic)")
    print("   AgentCore 研修デモ: ローカル実行版")
    print("   終了するには 'quit' または 'exit' と入力")
    print("=" * 60)
    print()

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
