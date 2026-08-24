#!/bin/bash
# ========================================
# AgentCore Runtime デプロイスクリプト
# ========================================
#
# 注意: このスクリプトはリファレンスです。
# 実際のデモではマネジメントコンソールからの操作を推奨します。
#
# 使い方:
#   ./deploy.sh [agent-runtime-name]

set -e

AGENT_NAME="${1:-secretary-agent}"
REGION="${AWS_REGION:-us-east-1}"

echo "================================================"
echo "🚀 AgentCore Runtime デプロイ"
echo "   Agent: ${AGENT_NAME}"
echo "   Region: ${REGION}"
echo "================================================"
echo ""

# ========================================
# Step 1: コンテナイメージのビルド
# ========================================
echo "📌 Step 1: Docker イメージビルド"
cd "$(dirname "$0")/../src"
docker build -t "${AGENT_NAME}:latest" .
echo "✅ ビルド完了"
echo ""

# ========================================
# Step 2: ECR にプッシュ
# ========================================
echo "📌 Step 2: ECR にプッシュ"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${AGENT_NAME}"

# ECR リポジトリ作成 (存在しない場合)
aws ecr describe-repositories --repository-names "${AGENT_NAME}" --region "${REGION}" 2>/dev/null \
    || aws ecr create-repository --repository-name "${AGENT_NAME}" --region "${REGION}"

# ECR ログイン
aws ecr get-login-password --region "${REGION}" | docker login --username AWS --password-stdin "${ECR_REPO}"

# タグ付け & プッシュ
docker tag "${AGENT_NAME}:latest" "${ECR_REPO}:latest"
docker push "${ECR_REPO}:latest"
echo "✅ ECR プッシュ完了: ${ECR_REPO}:latest"
echo ""

# ========================================
# Step 3: AgentCore Runtime 情報表示
# ========================================
echo "📌 Step 3: AgentCore Runtime の状態確認"
echo ""
echo "  以下のコマンドで Runtime を確認できます:"
echo ""
echo "  # Runtime 一覧"
echo "  aws bedrock-agentcore-control list-agent-runtimes \\"
echo "      --query 'agentRuntimes[].agentRuntimeName' --output table"
echo ""
echo "  # エンドポイント一覧"
echo "  aws bedrock-agentcore-control list-agent-runtime-endpoints \\"
echo "      --agent-runtime-id <RUNTIME_ID> --output table"
echo ""

echo "================================================"
echo "✅ デプロイ完了"
echo ""
echo "次のステップ:"
echo "  1. マネジメントコンソールで Runtime を確認"
echo "  2. エンドポイントが READY になるまで待機"
echo "  3. invoke_test.sh でテスト実行"
echo "================================================"
