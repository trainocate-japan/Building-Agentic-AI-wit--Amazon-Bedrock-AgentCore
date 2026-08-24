/**
 * AgentCore 呼び出し — SigV4 認証の仕組み
 *
 * このファイルは Next.js API Route として動作し、AWS SDK v3 の
 * 自動 SigV4 署名を利用して Bedrock AgentCore を呼び出します。
 *
 * ── SigV4 認証フロー ──
 * 1. BedrockAgentCoreClient 生成時に Credential Provider Chain が起動
 * 2. Amplify Hosting のサービスロールから一時認証情報を自動取得
 *    (環境変数: AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN)
 * 3. client.send() 実行時に SDK が自動で SigV4 署名ヘッダーを付与
 *    - Authorization: AWS4-HMAC-SHA256 Credential=.../SignedHeaders=.../Signature=...
 *    - X-Amz-Date: 20260805T...Z
 *    - X-Amz-Security-Token: (一時認証情報のセッショントークン)
 * 4. AgentCore エンドポイントが署名を検証し、IAM ポリシーで認可判定
 *
 * ── 必要な IAM ポリシー (Amplify サービスロールに付与) ──
 * {
 *   "Effect": "Allow",
 *   "Action": "bedrock-agentcore:InvokeAgentRuntime",
 *   "Resource": "<AGENT_RUNTIME_ARN>"
 * }
 */

import { NextRequest, NextResponse } from 'next/server'
import {
  BedrockAgentCoreClient,
  InvokeAgentRuntimeCommand,
} from '@aws-sdk/client-bedrock-agentcore'

const AGENT_ARN = process.env.NEXT_PUBLIC_AGENT_ARN || ''
const QUALIFIER = process.env.NEXT_PUBLIC_AGENT_QUALIFIER || 'prod'
const REGION = process.env.AWS_REGION || 'us-east-1'

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { prompt, actor_id } = body

    if (!prompt) {
      return NextResponse.json({ error: 'No prompt' }, { status: 400 })
    }

    // ┌─────────────────────────────────────────────────────────┐
    // │ SigV4 認証: SDK が自動で署名を付与                        │
    // │ - credentials を明示しない → Credential Provider Chain    │
    // │ - Amplify 環境では IAM サービスロールの一時認証情報を使用   │
    // │ - ローカル開発では ~/.aws/credentials or 環境変数を使用    │
    // └─────────────────────────────────────────────────────────┘
    const client = new BedrockAgentCoreClient({ region: REGION })

    const payload = JSON.stringify({ prompt, actor_id })

    const command = new InvokeAgentRuntimeCommand({
      agentRuntimeArn: AGENT_ARN,
      qualifier: QUALIFIER,
      payload: new TextEncoder().encode(payload),
    })

    // SDK が SigV4 署名付きの HTTPS リクエストを送信
    const response = await client.send(command)

    // ストリーミングレスポンスを SSE として転送
    const stream = new ReadableStream({
      async start(controller) {
        try {
          if (response.response) {
            for await (const chunk of response.response as AsyncIterable<Uint8Array>) {
              let text = new TextDecoder().decode(chunk)
              if (text.startsWith('"') && text.endsWith('"')) {
                try { text = JSON.parse(text) } catch {}
              }
              text = text.replace(/\\n/g, '\n')
              controller.enqueue(new TextEncoder().encode(text))
            }
          }
        } catch (e) {
          const errorMsg = e instanceof Error ? e.message : 'Unknown error'
          controller.enqueue(new TextEncoder().encode(`[Error: ${errorMsg}]`))
        } finally {
          controller.close()
        }
      },
    })

    return new NextResponse(stream, {
      headers: {
        'Content-Type': 'text/plain; charset=utf-8',
        'Cache-Control': 'no-cache',
        Connection: 'keep-alive',
      },
    })
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Internal error'
    return NextResponse.json({ error: message }, { status: 500 })
  }
}
