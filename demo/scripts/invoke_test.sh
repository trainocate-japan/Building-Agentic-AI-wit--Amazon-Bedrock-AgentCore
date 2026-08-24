#!/bin/bash
# ========================================
# AgentCore エンドポイント 動作確認スクリプト
# ========================================

set -e

# デフォルト設定
ENDPOINT_URL="${1:-http://localhost:8080}"
PROMPT="${2:-今日のスケジュールを教えてください}"

echo "================================================"
echo "🧪 AgentCore エージェント動作確認"
echo "   Endpoint: ${ENDPOINT_URL}"
echo "================================================"
echo ""

# ヘルスチェック
echo "📌 Step 1: ヘルスチェック (/ping)"
echo "---"
curl -s "${ENDPOINT_URL}/ping" | python3 -m json.tool
echo ""
echo ""

# エージェント呼び出し
echo "📌 Step 2: エージェント呼び出し (/invocations)"
echo "   Prompt: ${PROMPT}"
echo "---"
curl -s -X POST "${ENDPOINT_URL}/invocations" \
    -H "Content-Type: application/json" \
    -d "{\"input\": {\"prompt\": \"${PROMPT}\", \"session_id\": \"test-session-001\"}}" \
    | python3 -m json.tool
echo ""

# 追加テスト: ツール利用
echo ""
echo "📌 Step 3: ツール利用テスト"
echo "   Prompt: 東京の天気を教えて"
echo "---"
curl -s -X POST "${ENDPOINT_URL}/invocations" \
    -H "Content-Type: application/json" \
    -d '{"input": {"prompt": "東京の天気を教えて", "session_id": "test-session-001"}}' \
    | python3 -m json.tool
echo ""

echo "================================================"
echo "✅ テスト完了"
echo "================================================"
