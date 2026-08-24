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
    const { prompt, actor_id, session_id } = body

    if (!prompt) {
      return NextResponse.json({ error: 'No prompt' }, { status: 400 })
    }

    // AgentCore クライアント（SigV4 認証 — サーバーサイドの AWS 認証情報を使用）
    const client = new BedrockAgentCoreClient({ region: REGION })

    const payload = JSON.stringify({ prompt, actor_id })

    const command = new InvokeAgentRuntimeCommand({
      agentRuntimeArn: AGENT_ARN,
      qualifier: QUALIFIER,
      runtimeSessionId: session_id || undefined,
      payload: new TextEncoder().encode(payload),
    })

    const response = await client.send(command)

    // ストリーミングレスポンスを SSE として転送
    const stream = new ReadableStream({
      async start(controller) {
        try {
          if (response.response) {
            for await (const chunk of response.response as AsyncIterable<Uint8Array>) {
              let text = new TextDecoder().decode(chunk)
              // JSON 文字列の引用符を除去（"..." で囲まれている場合）
              if (text.startsWith('"') && text.endsWith('"')) {
                try { text = JSON.parse(text) } catch {}
              }
              // エスケープされた改行を実際の改行に変換
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
