#!/bin/bash
# ========================================
# AgentCore デモ環境セットアップスクリプト
# ========================================

set -e

echo "================================================"
echo "🚀 AgentCore Demo - Environment Setup"
echo "================================================"
echo ""

# Python バージョン確認
echo "📌 Python バージョン確認..."
python3 --version || { echo "❌ Python 3.11+ が必要です"; exit 1; }

# 仮想環境作成
echo ""
echo "📌 仮想環境を作成中..."
cd "$(dirname "$0")/../src"
python3 -m venv .venv
source .venv/bin/activate

# 依存パッケージインストール
echo ""
echo "📌 依存パッケージをインストール中..."
pip install --upgrade pip
pip install -r requirements.txt

# AWS CLI 確認
echo ""
echo "📌 AWS CLI 確認..."
aws --version || { echo "❌ AWS CLI v2 が必要です"; exit 1; }

# Bedrock モデルアクセス確認
echo ""
echo "📌 Bedrock モデルアクセス確認..."
aws bedrock list-foundation-models \
    --region us-east-1 \
    --query "modelSummaries[?modelId=='amazon.nova-pro-v1:0'].modelId" \
    --output text && echo "✅ Amazon Nova Pro アクセス確認済み" \
    || echo "⚠️  モデルアクセスを確認してください"

# AgentCore CLI 確認 (optional)
echo ""
echo "📌 AgentCore CLI 確認..."
which agentcore && echo "✅ AgentCore CLI インストール済み" \
    || echo "ℹ️  AgentCore CLI は未インストール (コンソールからの操作で代替可能)"

echo ""
echo "================================================"
echo "✅ セットアップ完了！"
echo ""
echo "次のステップ:"
echo "  source src/.venv/bin/activate"
echo "  cd src"
echo "  python -u agent.py"
echo "================================================"
