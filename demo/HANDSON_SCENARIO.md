# AgentCore デモエージェント ハンズオンシナリオ

## シナリオ概要

**「秘書エージェント（Secretary Agent）」** を段階的に構築し、AgentCore の各コンポーネントを講義モジュールに沿って実際に動かしながら学ぶハンズオンです。

### デモエージェントのコンセプト

講師の秘書として以下を行うエージェントを構築します:

- スケジュール確認・天気情報の取得（ツール利用のデモ）
- ユーザーの好みや過去の指示を記憶（メモリのデモ）
- 外部 API を安全に呼び出す（Identity / Gateway のデモ）
- 本番環境で動作状況を監視（Observability のデモ）

### 前提条件

| 項目 | 要件 |
|:--|:--|
| AWS アカウント | Bedrock AgentCore が利用可能なリージョン (us-east-1 推奨) |
| Bedrock モデルアクセス | Anthropic Claude Sonnet 4 (us.anthropic.claude-sonnet-4-6) ※SSM で管理 |
| Python | 3.11 以上 |
| AWS CLI | v2 最新版 (設定済み) |
| IAM 権限 | AgentCore 関連の Full Access |

---

## 全体アーキテクチャ

```
┌──────────────────────────────────────────────────────────────┐
│  ブラウザ (React + Amplify UI)                                │
│    └── Cognito ログイン → JWT Token                           │
└────────────────────────┬─────────────────────────────────────┘
                         │ Authorization: Bearer <JWT>
                         ▼
┌──────────────────────────────────────────────────────────────┐
│  API Gateway (Cognito Authorizer) ← インバウンド認証          │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│  AgentCore Runtime                                            │
│    Secretary Agent (Strands SDK)                               │
│      ├── config: SSM Parameter Store (プロンプト/モデルID)     │
│      ├── tools: MCPClient → AgentCore Gateway (SigV4)         │
│      └── memory: AgentCore Memory                             │
└────────────────────────┬─────────────────────────────────────┘
                         │ MCP Protocol (Streamable HTTP)
                         ▼
┌──────────────────────────────────────────────────────────────┐
│  AgentCore Gateway                                            │
│    ├── Lambda Target: get_schedule (yamamanx.com スクレイピング)│
│    └── Lambda Target: get_weather (OpenWeatherMap API)         │
│                          └── API Key via Identity              │
│                               (アウトバウンド認証)             │
└──────────────────────────────────────────────────────────────┘
```

---

## デモの進行フロー（モジュール対応）

| Phase | 対応モジュール | デモ内容 | 所要時間 |
|:--|:--|:--|:--|
| Phase 0 | 事前準備 | SSM Parameter Store でプロンプト管理 | 5 分 |
| Phase 1 | Mod 01 (Foundations) | ローカルで Strands Agent を動かす | 10 分 |
| Phase 2 | Mod 02 (Runtime) | AgentCore Runtime にデプロイ | 15 分 |
| Phase 3 | Mod 03 (Security) | Workload Identity を設定 | 10 分 |
| Phase 4 | Mod 04 (Tools/Gateway) | カスタムツール追加 + Gateway 連携 | 15 分 |
| Phase 5 | Mod 05 (Memory) | Memory を追加して会話を記憶 | 10 分 |
| Phase 6 | Mod 06 (Observability) | トレース確認・CloudWatch ダッシュボード | 10 分 |

---

## Phase 0: SSM Parameter Store のセットアップ（事前準備）

### 目的
- システムプロンプトとモデル ID を外部管理する
- 再デプロイなしでプロンプトを変更可能にする
- バージョン履歴による変更追跡

### 手順

1. **マネジメントコンソール（または CLI）:** SSM Parameter Store にパラメータを作成
   - `/agentcore/secretary-agent/system-prompt` — システムプロンプト
   - `/agentcore/secretary-agent/model-id` — モデル ID (us.anthropic.claude-sonnet-4-6)
2. IAM: エージェントの実行ロールに `ssm:GetParameter` 権限を付与

### 講義ポイント
- 「プロンプトはコードではない。独立してバージョン管理すべき」
- Bedrock Prompt Management はモデルとセットの設計 → Strands Agent には Parameter Store が適切
- 本番運用ではプロンプトの A/B テストやロールバックも可能

---

## Phase 1: ローカルでエージェントを動かす（Mod 01 対応）

### 目的
- Strands Agent SDK の基本を理解する
- エージェントの「考える → 回答する」ループを体感する
- ツールなしの状態での限界を認識する

### 手順

1. プロジェクトのセットアップ（venv、pip install）
2. 基本的な Strands Agent の作成と実行（`agent.py`）
3. エージェントとの対話を確認
4. プロンプト変更のライブデモ（Parameter Store 書き換え → 再起動）

### 講義ポイント
- 「プロトタイプは簡単に作れる。しかし本番化には何が必要か？」という問いかけ
- AgentCore が解決する Prototype-to-Production Chasm の説明
- ツールがなければ外部情報にアクセスできない限界

---

## Phase 2: AgentCore Runtime にデプロイ（Mod 02 対応）

### 目的
- AgentCore Runtime の仕組み（microVM によるセッション分離）を理解する
- コンソールからランタイムを作成しデプロイする

### 手順

1. **マネジメントコンソール:** AgentCore Runtime を作成
2. コンテナ化のための `Dockerfile` と `requirements.txt` を準備
   - Dockerfile は `opentelemetry-instrument python agent_production.py` で起動（自動計装）
3. AgentCore CLI または コンソールからデプロイ
4. 環境変数を設定:
   - `GATEWAY_URL` — Gateway の MCP エンドポイント
   - `AGENTCORE_MEMORY_ID` — Memory の ID
   - `MEMORY_PREFERENCE_STRATEGY_ID` — USER_PREFERENCE 戦略 ID
   - `MEMORY_SEMANTIC_STRATEGY_ID` — SEMANTIC 戦略 ID
5. エンドポイント経由でエージェントを呼び出し

### 講義ポイント
- microVM によるセッション分離（Q9 の内容）
- エンドポイントバージョニングの活用
- 最大 8 時間のセッション持続

---

## Phase 3: Workload Identity の設定（Mod 03 対応）

### 目的
- エージェントに永続的なアイデンティティを付与する
- アウトバウンド認証（API Key）で外部 API に安全にアクセスする
- インバウンド認証（Cognito）の概念を理解する

### 手順

1. OpenWeatherMap の無料アカウント作成、API Key 取得
2. **マネジメントコンソール:** Workload Identity を作成
3. Credential Provider（API Key タイプ）に OpenWeatherMap Key を登録
4. Lambda 環境変数に API Key を設定し、天気 Lambda を実 API 版に更新
5. AWS CLI で作成した Identity を確認

### 講義ポイント
- ワークロードアイデンティティ = 環境非依存のデジタルアンカー
- インバウンド: 「誰がエージェントを使っているか」（Cognito）
- アウトバウンド: 「エージェントが何にアクセスしているか」（API Key / OAuth）
- IAM サービスリンクロール `AWSServiceRoleForBedrockAgentCoreRuntimeIdentity`

---

## Phase 4: ツール追加と Gateway 連携（Mod 04 対応）

### 目的
- AgentCore Gateway でツールを統合管理する仕組みを理解する
- Lambda ターゲットでサーバーレスにツールを実装する
- MCP プロトコルによるツール自動検出を体感する

### 手順

1. Lambda 関数を2つ作成:
   - `agentcore-schedule-tool` — yamamanx.com/profile/ からスケジュール取得
   - `agentcore-weather-tool` — OpenWeatherMap API で天気取得
2. **マネジメントコンソール:** AgentCore Gateway を作成（IAM 認証）
3. Gateway に Lambda ターゲットを追加（tool schema 付き）
4. `agent_with_gateway.py` で Gateway 経由のツール自動検出・利用をデモ

### 講義ポイント
- Gateway にツールを追加するだけでエージェントのコード変更不要
- ローカル MCP vs リモート MCP のホスティング戦略
- Gateway による認証の一元管理
- ツール自動検出（tools/list）の威力

---

## Phase 5: Memory の追加（Mod 05 対応）

### 目的
- 短期メモリと長期メモリの違いを理解する
- ユーザープリファレンスの永続化を体感する

### 手順

1. **マネジメントコンソール:** AgentCore Memory を作成
   - 短期メモリ（イベント保持期間）を設定
   - 長期メモリ戦略（USER_PREFERENCE + SEMANTIC）を追加
2. エージェントコードに Memory を統合
3. 会話テスト：好みを伝えて → セッション切断 → 再接続して記憶を確認

### 講義ポイント
- 短期 vs 長期 vs エピソディック メモリ（Q4, Q11）
- ユーザープリファレンス戦略の namespace 設計
- 長期メモリ vs RAG の使い分け

---

## Phase 6: Observability の確認（Mod 06 対応）

### 目的
- OpenTelemetry ベースのトレーシングを理解する
- CloudWatch GenAI Observability ダッシュボードを確認する

### 手順

1. Dockerfile で `opentelemetry-instrument` コマンドによる自動計装が有効であることを確認
2. AgentCore Runtime にデプロイ
3. エージェントに複数の質問を投げてトレースを生成
4. **マネジメントコンソール:** CloudWatch → GenAI Observability ダッシュボードで確認
5. セッション・トレース・スパンの階層構造を解説

### 講義ポイント
- Strands SDK は `strands.telemetry.tracer` スコープで自動計装
- スパンレベルでのツールパラメータ精度評価（Q7）
- AgentCore Evaluations の組み込みエバリュエータ

---

## ファイル構成

```
demo/
├── HANDSON_SCENARIO.md              # 本ファイル（シナリオ全体）
├── lambda/
│   ├── schedule_tool/
│   │   └── lambda_function.py       # yamamanx.com スクレイピング版
│   ├── weather_tool/
│   │   └── lambda_function.py       # OpenWeatherMap 実API版
│   └── tool_schemas/
│       ├── schedule_tools.json      # Gateway 登録用スキーマ
│       └── weather_tools.json       # Gateway 登録用スキーマ
├── src/
│   ├── config.py                    # 設定管理（SSM Parameter Store）
│   ├── agent.py                     # Phase 1: ローカル実行用（ツールなし）
│   ├── agent_with_gateway.py        # Phase 4: Gateway 経由ツール利用（ローカル開発用）
│   ├── agent_production.py          # Runtime デプロイ用 (BedrockAgentCoreApp + Memory + Gateway)
│   ├── Dockerfile                   # AgentCore Runtime 用 (opentelemetry-instrument で自動計装)
│   └── requirements.txt             # 依存: bedrock-agentcore[strands-agents], aws-opentelemetry-distro
├── frontend/
│   ├── src/App.jsx                  # React チャット UI
│   ├── src/main.jsx                 # Amplify/Cognito 設定
│   ├── src/styles.css               # スタイル
│   ├── package.json                 # npm 依存
│   └── .env.example                 # 環境変数テンプレート
├── console_guide/
│   ├── 00_create_parameters.md      # Parameter Store 作成手順
│   ├── 00b_phase1_local_agent.md    # Phase 1 ローカル実行手順
│   ├── 01_create_runtime.md         # Runtime 作成手順
│   ├── 02_create_identity.md        # Identity 作成手順
│   ├── 03_create_gateway.md         # Gateway 作成手順
│   ├── 04_create_memory.md          # Memory 作成手順
│   ├── 05_observability.md          # Observability 確認手順
│   └── 06_frontend_cognito.md       # Cognito + フロントエンド手順
└── scripts/
    ├── setup.sh                     # 環境セットアップ
    ├── setup_parameters.sh          # Parameter Store セットアップ
    ├── deploy.sh                    # デプロイスクリプト
    └── invoke_test.sh               # 動作確認スクリプト
```

---

## 事前準備チェックリスト

- [ ] AWS CLI v2 がインストール・設定済み
- [ ] Python 3.11+ がインストール済み
- [ ] Node.js 18+ がインストール済み（フロントエンド用）
- [ ] Bedrock モデルアクセスが有効（Anthropic Claude Sonnet 4）
- [ ] AgentCore 利用リージョン（us-east-1）の確認
- [ ] IAM ロール・ポリシーの準備
- [ ] OpenWeatherMap 無料アカウント・API Key 取得済み
- [ ] (Optional) Docker Desktop がインストール済み

---

## 次のステップ（秘書エージェント拡張計画）

このデモエージェントは研修後に以下の方向で拡張可能です:

1. **Multi-Agent 構成**: 調査担当・スケジュール担当の sub-agent を追加
2. **RAG 統合**: Amazon Bedrock Knowledge Bases と連携
3. **Slack / Teams 連携**: Gateway 経由でチャットツールと統合
4. **評価パイプライン**: AgentCore Evaluations で品質を継続監視
5. **DynamoDB 永続化**: スケジュール追加を永続的に保存
6. **Cognito フロントエンド**: Web UI からのインバウンド認証（`console_guide/06_frontend_cognito.md` 参照）
