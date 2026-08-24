# Phase 2: AgentCore Runtime の作成（Module 02 対応）

## 概要

AgentCore Runtime にエージェントをデプロイし、マネージドなエンドポイントとして公開します。
microVM によるセッション分離・自動スケーリングが提供されます。

---

## Step 1: ローカルでの動作確認（事前準備）

まず Phase 1 のエージェントが正常に動作することを確認します。

```bash
cd demo/src
source .venv/bin/activate
python -u agent.py
```

> 💡 講義ポイント: 「これはローカルで動いている。本番で複数ユーザーが同時にアクセスしたら？セッション間のデータ漏洩は？スケーリングは？」

---

## Step 2: コンテナイメージの準備

### 2-1. Dockerfile の確認

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8080
# OTelのPython SDK経由でアプリを起動（自動計装を有効化）
CMD ["opentelemetry-instrument", "python", "agent_production.py"]
```

> 💡 **ポイント**: `opentelemetry-instrument` で起動することで、Strands SDK のトレースが自動的に CloudWatch に送信されます。`requirements.txt` に `aws-opentelemetry-distro` が必要です。

### 2-2. ローカルでビルド & テスト

```bash
cd demo/src
docker build -t secretary-agent:latest .
docker run -p 8080:8080 \
    -e AWS_ACCESS_KEY_ID \
    -e AWS_SECRET_ACCESS_KEY \
    -e AWS_SESSION_TOKEN \
    -e AWS_REGION=us-east-1 \
    secretary-agent:latest
```

別ターミナルでテスト:
```bash
cd demo/scripts
./invoke_test.sh http://localhost:8080
```

### 2-3. ECR にプッシュ

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=us-east-1
ECR_REPO="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/secretary-agent"

# ECR リポジトリ作成
aws ecr create-repository --repository-name secretary-agent --region ${REGION}

# ログイン & プッシュ
aws ecr get-login-password --region ${REGION} | \
    docker login --username AWS --password-stdin ${ECR_REPO}

docker tag secretary-agent:latest ${ECR_REPO}:latest
docker push ${ECR_REPO}:latest
```

---

## Step 3: マネジメントコンソールで Runtime を作成

### 3-1. AgentCore コンソールを開く

1. AWS マネジメントコンソールにログイン
2. サービス検索で **「Bedrock」** → **「AgentCore」** セクションへ移動
3. 左ナビゲーションから **「Agent runtimes」** を選択

### 3-2. Runtime の作成

1. **「Create agent runtime」** をクリック

2. 基本設定:
   | 項目 | 値 |
   |:--|:--|
   | Runtime name | `secretary_agent_runtime` |
   | Description | `研修デモ用の秘書エージェント` |

3. コンテナ設定:
   | 項目 | 値 |
   |:--|:--|
   | Container image URI | `<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/secretary-agent:latest` |

4. IAM ロール:
   - 新規作成、または事前に作成した実行ロールを選択
   - 必要な権限: Bedrock InvokeModel, ECR Pull, CloudWatch Logs, SSM GetParameter

5. 環境変数の設定:
   | 環境変数 | 説明 | 値の例 |
   |:--|:--|:--|
   | `GATEWAY_URL` | AgentCore Gateway の MCP エンドポイント | `https://<gateway-id>.bedrock-agentcore.us-east-1.amazonaws.com/mcp` |
   | `AGENTCORE_MEMORY_ID` | AgentCore Memory の ID | `mem-xxxxxxxx` |
   | `MEMORY_PREFERENCE_STRATEGY_ID` | USER_PREFERENCE 戦略 ID | `strat-xxxxxxxx` |
   | `MEMORY_SEMANTIC_STRATEGY_ID` | SEMANTIC 戦略 ID | `strat-yyyyyyyy` |
   | `AWS_REGION` | リージョン (default: us-east-1) | `us-east-1` |
   | `PARAMETER_PREFIX` | SSM パラメータのプレフィックス | `/agentcore/secretary-agent` |

   > 💡 Gateway と Memory は Phase 4, 5 で作成後に設定します。初回デプロイ時は空でも起動可能です。

6. **「Create」** をクリック

### 3-3. ステータスの確認

- ステータスが `CREATING` → `READY` になるまで待機（2-5分）
- AWS CLI でも確認可能:

```bash
aws bedrock-agentcore-control list-agent-runtimes \
    --query "agentRuntimes[].{Name:agentRuntimeName, Status:status}" \
    --output table
```

---

## Step 4: エンドポイントの作成

### 4-1. コンソールからエンドポイント作成

1. 作成した Runtime をクリック
2. **「Endpoints」** タブ → **「Create endpoint」**

3. 設定:
   | 項目 | 値 |
   |:--|:--|
   | Endpoint name | `prod` |
   | Version | (Latest) |

4. **「Create endpoint」** をクリック

### 4-2. ステータス確認

コンソールでエンドポイントのステータスが `READY` になるまで待機（2-5分）。

> Gateway 連携後に Phase 4 で動作確認を行います。

---

## 講義ポイントまとめ

| トピック | 説明 |
|:--|:--|
| microVM 分離 | 各セッションは専用の microVM で実行。メモリ・ファイルシステムが完全分離 |
| 自動スケーリング | リクエスト数に応じて microVM が自動的にスケール |
| セッション持続 | 最大 8 時間のロングランニングセッションをサポート |
| バージョニング | エンドポイントのバージョンを管理し、Blue/Green デプロイが可能 |
| フレームワーク非依存 | Strands, LangChain, CrewAI など任意のフレームワークをそのまま利用可能 |

> 💡 「同じコードがローカルでもクラウドでも動く。AgentCore Runtime はインフラを抽象化し、開発者はエージェントのロジックに集中できる」
