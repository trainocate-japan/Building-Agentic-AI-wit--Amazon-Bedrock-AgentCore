#!/bin/bash
# ========================================
# SSM Parameter Store セットアップスクリプト
# ========================================
#
# 秘書エージェントのシステムプロンプトとモデルIDを
# SSM Parameter Store に登録します。
#
# 使い方:
#   ./setup_parameters.sh [region]

set -e

REGION="${1:-us-east-1}"
PREFIX="/agentcore/secretary-agent"

echo "================================================"
echo "📦 SSM Parameter Store セットアップ"
echo "   Region: ${REGION}"
echo "   Prefix: ${PREFIX}"
echo "================================================"
echo ""

# ========================================
# システムプロンプト
# ========================================
echo "📌 Step 1: システムプロンプトを登録..."

SYSTEM_PROMPT="あなたは優秀な秘書エージェントです。名前は「セクレタリー」です。

以下の方針で行動してください:
- 簡潔で正確な情報を提供する
- 日本語で応答する
- 不明な点があれば確認を取る
- ユーザーの時間を無駄にしない

あなたは研修講師の秘書として、スケジュール管理や情報収集を支援します。"

aws ssm put-parameter \
    --name "${PREFIX}/system-prompt" \
    --type "String" \
    --value "${SYSTEM_PROMPT}" \
    --description "秘書エージェントのシステムプロンプト" \
    --region "${REGION}" \
    --overwrite 2>/dev/null \
    && echo "   ✅ ${PREFIX}/system-prompt を登録しました" \
    || echo "   ❌ 登録に失敗しました"

echo ""

# ========================================
# モデル ID
# ========================================
echo "📌 Step 2: モデル ID を登録..."

aws ssm put-parameter \
    --name "${PREFIX}/model-id" \
    --type "String" \
    --value "us.amazon.nova-pro-v1:0" \
    --description "使用する Bedrock モデルの ID" \
    --region "${REGION}" \
    --overwrite 2>/dev/null \
    && echo "   ✅ ${PREFIX}/model-id を登録しました" \
    || echo "   ❌ 登録に失敗しました"

echo ""

# ========================================
# 確認
# ========================================
echo "📌 Step 3: 登録内容を確認..."
echo ""
aws ssm get-parameters-by-path \
    --path "${PREFIX}" \
    --query "Parameters[].{Name:Name, Version:Version}" \
    --output table \
    --region "${REGION}"

echo ""
echo "================================================"
echo "✅ セットアップ完了！"
echo ""
echo "エージェントを起動できます:"
echo "  cd demo/src"
echo "  python -u agent.py"
echo ""
echo "プロンプトを変更するには:"
echo "  aws ssm put-parameter \\"
echo "      --name '${PREFIX}/system-prompt' \\"
echo "      --type String --overwrite \\"
echo "      --value '新しいプロンプト' \\"
echo "      --region ${REGION}"
echo "================================================"
