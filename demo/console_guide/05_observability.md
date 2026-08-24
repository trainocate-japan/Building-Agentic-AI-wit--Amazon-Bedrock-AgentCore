# Phase 6: Observability の確認（Module 06 対応）

## 概要

AgentCore Observability で、エージェントの動作を OpenTelemetry ベースの
トレースとして可視化し、CloudWatch GenAI Observability ダッシュボードで確認します。

---

## Step 1: コンセプトの説明

> 💡 講義ポイント: 「エージェントが間違った回答をしたとき、
> なぜそうなったか追跡できるか？どのツールを呼んだ？どんな推論をした？
> Observability なしでは本番運用は不可能」

### テレメトリの階層構造

```
Session (1回の対話全体)
  └── Trace (1つのリクエスト処理)
        ├── Span: LLM Invocation (モデル呼び出し)
        ├── Span: Tool Call - get_schedule (ツール実行)
        ├── Span: LLM Invocation (ツール結果を踏まえて再推論)
        └── Span: Final Response (最終応答生成)
```

### Strands SDK の自動計装

- Strands SDK は `strands.telemetry.tracer` スコープで自動的にスパンを生成
- 追加のインストルメンテーションライブラリ不要
- AgentCore Runtime 上では `session.id` 属性が自動注入

---

## Step 2: Observability の設定

### 2-1. Dockerfile での自動計装

`agent_production.py` は Dockerfile で `opentelemetry-instrument` コマンド経由で起動されるため、
追加のコード変更なしにトレースが自動生成されます。

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

> ⚠️ **重要**: `opentelemetry-instrument` コマンドは `aws-opentelemetry-distro` パッケージに含まれています。`requirements.txt` に以下が必要です:
> ```
> aws-opentelemetry-distro>=0.10.0
> ```

### 2-2. 依存パッケージの確認

`requirements.txt` に以下が含まれていることを確認:

```
# Observability (Runtime が自動計装で使用)
aws-opentelemetry-distro>=0.10.0
```

### 2-3. 環境変数の設定（オプション）

```bash
# エージェント名（CloudWatch でのフィルタリング用）
export OTEL_SERVICE_NAME="secretary-agent"

# リソース属性
export OTEL_RESOURCE_ATTRIBUTES="service.name=secretary-agent"
```

### 2-4. 計装の仕組み

AgentCore Runtime にデプロイしている場合:
- Dockerfile の `CMD ["opentelemetry-instrument", "python", "agent_production.py"]` により自動計装
- 追加設定は不要（AgentCore Runtime が CloudWatch エンドポイントを自動設定）

ローカルでトレースを確認したい場合のみ:

```bash
cd demo/src
pip install aws-opentelemetry-distro
opentelemetry-instrument python agent_with_gateway.py
```

> この状態で `/invocations` にリクエストを送ると、トレースが CloudWatch に送信されます。

---

## Step 3: トレースデータの生成

### 3-1. 複数のリクエストを送信

テストスクリプトで様々なパターンのリクエストを送り、トレースデータを蓄積します:

```bash
# テスト 1: 単純な質問（ツールなし）
curl -s -X POST http://localhost:8080/invocations \
    -H "Content-Type: application/json" \
    -d '{"input": {"prompt": "こんにちは", "session_id": "demo-session-01"}}'

# テスト 2: ツール呼び出し（1回）
curl -s -X POST http://localhost:8080/invocations \
    -H "Content-Type: application/json" \
    -d '{"input": {"prompt": "今日のスケジュールを教えて", "session_id": "demo-session-01"}}'

# テスト 3: 複数ツール呼び出し
curl -s -X POST http://localhost:8080/invocations \
    -H "Content-Type: application/json" \
    -d '{"input": {"prompt": "東京の天気を確認して、外出の予定を入れていい？", "session_id": "demo-session-01"}}'

# テスト 4: 別セッション
curl -s -X POST http://localhost:8080/invocations \
    -H "Content-Type: application/json" \
    -d '{"input": {"prompt": "明日の予定に会議を追加して", "session_id": "demo-session-02"}}'
```

---

## Step 4: CloudWatch GenAI Observability ダッシュボードの確認

### 4-1. ダッシュボードを開く

1. AWS マネジメントコンソール → **CloudWatch**
2. 左ナビゲーション → **「AI monitoring」** → **「GenAI Observability」**
3. エージェント名 `secretary-agent` でフィルタ

### 4-2. 確認するメトリクス

| メトリクス | 説明 | 見るべきポイント |
|:--|:--|:--|
| Invocation count | リクエスト総数 | トラフィックパターン |
| Latency (p50, p95, p99) | 応答時間 | SLA 遵守状況 |
| Error rate | エラー率 | 異常検知 |
| Token usage | トークン消費量 | コスト管理 |
| Tool invocation count | ツール呼び出し回数 | ツール利用パターン |

### 4-3. トレースの詳細確認

1. **「Traces」** タブを選択
2. 特定のトレースをクリック

確認するポイント:
- **推論チェーン**: LLM がどう判断したか
- **ツール選択**: なぜそのツールを選んだか
- **レイテンシ内訳**: どのスパンに時間がかかっているか
- **入出力**: 各スパンの入力と出力

### 4-4. セッション単位の確認

1. **「Sessions」** タブを選択
2. `demo-session-01` をクリック
3. 同一セッション内の全トレースを時系列で確認

> 💡 講義ポイント: 「ユーザーが『回答がおかしい』と報告したとき、
> セッション ID でフィルタして、そのユーザーの体験を完全に再現できる」

---

## Step 5: AgentCore Evaluations（概要説明）

### 5-1. 組み込みエバリュエータ

AgentCore には以下の評価指標が組み込まれています:

| エバリュエータ | レベル | 評価内容 |
|:--|:--|:--|
| Tool parameter accuracy | Span | ツール呼び出しのパラメータ正確性 |
| Tool selection | Span | 適切なツールを選択したか |
| Response quality | Trace | 最終回答の品質 |
| Hallucination detection | Trace | ハルシネーションの有無 |
| Task completion | Session | タスクが完了したか |

### 5-2. 評価の実行（コンセプト説明）

```python
# 概念的なコード例
from bedrock_agentcore.evaluations import EvaluationClient

eval_client = EvaluationClient(region_name="us-east-1")

# トレースデータに対して評価を実行
results = eval_client.evaluate(
    trace_id="<trace-id>",
    evaluators=["tool_parameter_accuracy", "response_quality"],
    ground_truth={
        "expected_tools": ["get_schedule"],
        "expected_response_contains": ["9:00", "Module 01"]
    }
)
```

> 💡 本格的な評価パイプラインの構築は「次のステップ」として紹介

---

## Step 6: アラートの設定（オプション）

### 6-1. CloudWatch Alarm の作成例

```bash
# エラー率が 5% を超えたらアラート
aws cloudwatch put-metric-alarm \
    --alarm-name "secretary-agent-error-rate" \
    --metric-name "ErrorRate" \
    --namespace "bedrock-agentcore" \
    --statistic Average \
    --period 300 \
    --evaluation-periods 2 \
    --threshold 5 \
    --comparison-operator GreaterThanThreshold \
    --dimensions Name=AgentName,Value=secretary-agent
```

---

## 講義ポイントまとめ

| トピック | 説明 |
|:--|:--|
| 自動計装 | Dockerfile の `opentelemetry-instrument` + `aws-opentelemetry-distro` で追加コードなしにトレース生成 |
| 階層構造 | Session → Trace → Span で粒度を選んで分析 |
| GenAI 特化 | トークン使用量、推論チェーン、ツール選択を可視化 |
| 評価連携 | トレースデータを使って品質評価を自動化 |
| マルチバックエンド | CloudWatch 以外に Datadog, Grafana にも送信可能 |

### Observability の3本柱（エージェント版）

| 柱 | 従来のアプリ | エージェント固有 |
|:--|:--|:--|
| Metrics | レイテンシ、エラー率 | トークン消費、ツール呼び出し頻度 |
| Traces | リクエストフロー | 推論チェーン、ツール選択プロセス |
| Logs | アプリケーションログ | LLM 入出力、メモリ取得ログ |

> 💡 「従来のアプリ監視では『何が起きたか』が分かる。
> エージェントの Observability では『なぜそう判断したか』まで分かる。
> これが本番運用の安心感を生む」
