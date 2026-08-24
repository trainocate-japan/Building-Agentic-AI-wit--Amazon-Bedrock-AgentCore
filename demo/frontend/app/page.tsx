'use client'

import { useState, useRef, useEffect, useMemo } from 'react'
import { useAuthenticator } from '@aws-amplify/ui-react'
import { fetchAuthSession } from 'aws-amplify/auth'
import ReactMarkdown from 'react-markdown'

interface Message {
  role: 'user' | 'assistant' | 'error'
  content: string
}

export default function ChatPage() {
  const { user, signOut } = useAuthenticator()
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [streamingText, setStreamingText] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // セッションIDを生成し、同一会話内で保持する
  const sessionId = useMemo(() => crypto.randomUUID(), [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingText])

  const sendMessage = async () => {
    if (!input.trim() || loading) return

    const userMessage = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: userMessage }])
    setLoading(true)
    setStreamingText('')

    try {
      // Cognito Access Token を取得
      const session = await fetchAuthSession()
      const token = session.tokens?.accessToken?.toString()

      if (!token) {
        throw new Error('認証トークンの取得に失敗しました')
      }

      // サーバーサイドの Route Handler を呼び出し
      const response = await fetch('/api/invoke', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: userMessage,
          actor_id: user?.username || 'default',
          session_id: sessionId,
          token,
        }),
      })

      if (!response.ok) {
        const errorText = await response.text()
        throw new Error(`HTTP ${response.status}: ${errorText}`)
      }

      // レスポンス処理
      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      let fullText = ''

      if (reader) {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          const chunk = decoder.decode(value, { stream: true })
          fullText += chunk
          setStreamingText(fullText)
        }
      }

      setStreamingText('')
      // テーブルの行間の余計な空行を除去（Markdownテーブルが壊れるのを防ぐ）
      const cleaned = fullText.replace(/\|\n\n\|/g, '|\n|')
      setMessages(prev => [...prev, { role: 'assistant', content: cleaned || 'エージェントからの応答がありません' }])
    } catch (error) {
      setStreamingText('')
      setMessages(prev => [...prev, {
        role: 'error',
        content: `エラー: ${error instanceof Error ? error.message : '不明なエラー'}`
      }])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // IME 変換中は無視
    if (e.nativeEvent.isComposing) return
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="chat-container">
      <header className="chat-header">
        <div className="header-left">
          <h1>Secretary Agent</h1>
          <span className="subtitle">AgentCore Demo</span>
        </div>
        <div className="header-right">
          <span className="username">{user?.username}</span>
          <button onClick={signOut} className="signout-btn">ログアウト</button>
        </div>
      </header>

      <div className="messages">
        {messages.length === 0 && !loading && (
          <div className="welcome">
            <p>こんにちは！秘書エージェント「セクレタリー」です。</p>
            <p>スケジュール管理や天気情報の取得をお手伝いします。</p>
            <div className="suggestions">
              <button onClick={() => setInput('今日のスケジュールを教えて')}>
                今日のスケジュール
              </button>
              <button onClick={() => setInput('東京の天気は？')}>
                東京の天気
              </button>
              <button onClick={() => setInput('私の趣味は何でしたっけ？')}>
                記憶の確認
              </button>
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}`}>
            <div className="message-icon">
              {msg.role === 'user' ? '👤' : msg.role === 'error' ? '⚠️' : '🤖'}
            </div>
            <div className="message-content">
              {msg.role === 'assistant' ? (
                <ReactMarkdown>{msg.content}</ReactMarkdown>
              ) : (
                <pre>{msg.content}</pre>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="message assistant">
            <div className="message-icon">🤖</div>
            <div className="message-content thinking">
              {streamingText ? (
                <ReactMarkdown>{streamingText}</ReactMarkdown>
              ) : (
                <div className="thinking-indicator">
                  <span className="dot" />
                  <span className="dot" />
                  <span className="dot" />
                </div>
              )}
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="input-area">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="メッセージを入力... (Enter で送信)"
          disabled={loading}
          rows={1}
        />
        <button onClick={sendMessage} disabled={loading || !input.trim()}>
          送信
        </button>
      </div>
    </div>
  )
}
