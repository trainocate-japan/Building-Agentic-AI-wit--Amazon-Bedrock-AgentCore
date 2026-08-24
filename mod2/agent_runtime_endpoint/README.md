# Module 02: AgentCore Runtime エンドポイント

## 概要

AgentCore Runtime にエージェントをデプロイするには、コンテナが以下の2つのエンドポイントを公開する必要があります:

| エンドポイント | メソッド | 用途 |
|:--|:--|:--|
| `/ping` | GET | ヘルスチェック（コンテナ起動確認） |
| `/invocations` | POST | エージェントインタラクション（本体） |

---

## アーキテクチャ

```
ユーザー → AgentCore Runtime → コンテナ (microVM)
                                  ├── GET  /ping         → "OK" (200)
                                  └── POST /invocations  → エージェント実行 → レスポンス
```

AgentCore Runtime は:
1. コンテナ起動後、`/ping` を呼んで正常起動を確認
2. ユーザーリクエストを `POST /invocations` に転送
3. レスポンスをユーザーに返す

---

## ファイル構成

```
mod2/
├── README.md                              ← このファイル
├── agent_endpoint.py                      ← FastAPI で手書きする方法（学習用）
├── agent_endpoint_bedrock_agentcore.py    ← BedrockAgentCoreApp 推奨パターン
├── Dockerfile                             ← コンテナイメージ定義
└── requirements.txt                       ← 依存パッケージ
```

---

## 方法 1: FastAPI で手書き（学習用）

`agent_endpoint.py` は、エンドポイントの仕組みを理解するために FastAPI で明示的に書いた例です。

### ポイント

```python
# ヘルスチェック - AgentCore が定期的に呼ぶ
@app.get("/ping")
async def ping():
    return PlainTextResponse("OK", status_code=200)

# エージェント呼び出し - ユーザーリクエストが来る
@app.post("/invocations")
async def invocations(request: Request):
    body = await request.json()
    user_input = body.get("prompt", "")
    # ... エージェント実行 ...
    return PlainTextResponse(response_text, status_code=200)
```

### `/ping` エンドポイントの役割

- AgentCore Runtime がコンテナの**ヘルスチェック**に使用
- `200 OK` を返すだけでよい（ボディの内容は問わない）
- コンテナ起動直後と、稼働中に定期的に呼ばれる
- レスポンスがなければ「異常」と判断され、コンテナが再起動される

### `/invocations` エンドポイントの役割

- エージェントの**メインロジック**が実行される場所
- AgentCore Runtime がユーザーリクエストをここに転送する
- リクエストボディ（JSON）にプロンプトやセッション情報が含まれる
- レスポンスがそのままユーザーに返される

---

## 方法 2: BedrockAgentCoreApp（推奨）

`agent_endpoint_bedrock_agentcore.py` は `bedrock-agentcore` パッケージの `BedrockAgentCoreApp` を使います。

### ポイント

```python
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()

@app.entrypoint
async def invoke(payload, context):
    """POST /invocations で自動的に呼ばれる"""
    user_input = payload.get("prompt", "")
    # ... エージェント実行 ...
    return response_text

app.run()  # /ping と /invocations が自動構成される
```

### メリット

| 特徴 | 説明 |
|:--|:--|
| ルーティング自動化 | `/ping` と `/invocations` を自分で定義する必要がない |
| コンテキスト管理 | `context.session_id` などのランタイム情報が自動で渡される |
| OTel 統合 | Observability の設定が組み込み済み |
| セッション管理 | microVM 単位でのセッション分離が透過的に実現 |

---

## ローカルテスト

### 方法 1 (FastAPI 手書き版)

```bash
cd demo/mod2
pip install -r requirements.txt
uvicorn agent_endpoint:app --host 0.0.0.0 --port 8080
```

### 方法 2 (BedrockAgentCoreApp 版)

```bash
cd demo/mod2
pip install -r requirements.txt
python agent_endpoint_bedrock_agentcore.py
```

### テストコマンド

```bash
# ヘルスチェック
curl http://localhost:8080/ping
# → OK

# エージェント呼び出し
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"prompt": "こんにちは、自己紹介してください"}'
```

---

## Docker でテスト

```bash
cd demo/mod2

# ビルド
docker build -t secretary-agent-mod2:latest .

# 実行（AWS 認証情報を渡す）
docker run -p 8080:8080 \
    -e AWS_ACCESS_KEY_ID \
    -e AWS_SECRET_ACCESS_KEY \
    -e AWS_SESSION_TOKEN \
    -e AWS_REGION=us-east-1 \
    secretary-agent-mod2:latest

# テスト
curl http://localhost:8080/ping
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"prompt": "今日の天気を教えて"}'
```

---

## 講義ポイント

| トピック | 説明 |
|:--|:--|
| 2エンドポイント契約 | AgentCore Runtime はコンテナに `/ping` と `/invocations` の2つだけを要求する |
| フレームワーク非依存 | FastAPI, Flask, Express 等どれでも OK。HTTP が返せればよい |
| ポート 8080 | AgentCore Runtime はデフォルトでポート 8080 にアクセスする |
| ステートレス設計 | 各リクエストは独立して処理される（状態は Memory 等の外部サービスで管理） |
| スターターツールキット | `BedrockAgentCoreApp` を使えば定型コードを書かずに済む |

> 💡 **キーメッセージ**: 「AgentCore Runtime との契約はシンプル — `/ping` で生存報告、`/invocations` で仕事をする。この2つさえ実装すれば、あとは AgentCore がスケーリング・分離・監視を全部やってくれる」
