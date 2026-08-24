# Phase 1: ローカルでエージェントを動かす（Module 01 対応）

## 概要

Strands Agent SDK を使ってローカル環境でエージェントを起動し、
「考える → 回答する」の基本ループを体感します。

---

## Step 1: Python 仮想環境のセットアップ

```bash
cd demo/src
python3 -m venv .venv
source .venv/bin/activate
```

## Step 2: 依存パッケージのインストール

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

主要パッケージ:
| パッケージ | 用途 |
|:--|:--|
| strands-agents | Strands Agent SDK 本体 |
| boto3 | AWS SDK（Bedrock 呼び出し、SSM 取得） |

## Step 3: AWS 認証情報の確認

```bash
# プロファイルを使う場合
export AWS_PROFILE=your-profile-name

# 認証が通ることを確認
aws sts get-caller-identity
```

## Step 4: Parameter Store の確認（Phase 0 で作成済み）

```bash
aws ssm get-parameter \
    --name "/agentcore/secretary-agent/system-prompt" \
    --query "Parameter.Value" \
    --output text \
    --region us-east-1
```

> システムプロンプトが表示されれば OK

## Step 5: エージェントの起動

```bash
python -u agent.py
```

起動時の出力例:
```
📌 設定を読み込み中...
   Model: us.amazon.nova-pro-v1:0
   Prompt: あなたは山下光洋の秘書エージェントです...

============================================================
🤖 Secretary Agent - Phase 1 (Basic)
   AgentCore 研修デモ: ローカル実行版
   終了するには 'quit' または 'exit' と入力
============================================================
```

## Step 6: 対話デモ

### 基本的な対話

```
👤 You: こんにちは、自己紹介してください
🤖 Secretary: 私は山下光洋さんの秘書エージェント「セクレタリー」です。
   スケジュール管理や情報収集のお手伝いをします。...

👤 You: 私のプロフィールを教えて
🤖 Secretary: 山下光洋さんのプロフィールです。
   トレノケート株式会社の技術教育エンジニアで、AWS認定インストラクター...
```

### ツールがない状態の限界を見せる

```
👤 You: 今日のスケジュールを教えて
🤖 Secretary: 申し訳ありませんが、現在スケジュールにアクセスする手段がないため、
   具体的な予定をお伝えすることができません。...
```

> 💡 講義ポイント: 「ツールがなければ LLM は知識から推測するしかない。
> Phase 4 でツールを追加すると、この問いに正確に答えられるようになる」

### プロンプトの影響を見せる（オプション）

Parameter Store でプロンプトを書き換えて再起動すると動作が変わることを見せる:

```bash
# 別ターミナルで
aws ssm put-parameter \
    --name "/agentcore/secretary-agent/system-prompt" \
    --type String --overwrite \
    --value "あなたは関西弁で話す秘書です。名前はセクレタリーやで。" \
    --region us-east-1

# エージェント側で Ctrl+C → 再起動
python -u agent.py
```

```
👤 You: こんにちは
🤖 Secretary: おおきに！セクレタリーやで。なんか手伝えることあるか？
```

> 💡 「コードは一切変えていない。プロンプトだけで動作が変わる。これがプロンプトエンジニアリング」

## Step 7: 終了

```
👤 You: quit
👋 お疲れ様でした！
```

---

## トラブルシューティング

| 症状 | 原因 | 対処 |
|:--|:--|:--|
| `AccessDeniedException` | Bedrock モデルアクセス未有効 | Bedrock コンソールでモデルアクセスをリクエスト |
| `ParameterNotFound` → デフォルト値使用 | Phase 0 未実施 | `setup_parameters.sh` を実行 |
| `NoCredentialProviders` | AWS 認証情報なし | `aws configure` または `AWS_PROFILE` を設定 |
| レスポンスが遅い | 初回はコールドスタート | 2回目以降は速くなる |

---

## 講義ポイントまとめ

| トピック | 説明 |
|:--|:--|
| 最小構成 | `Agent()` + `model` + `system_prompt` の3要素でエージェントが動く |
| Bedrock 統合 | `BedrockModel` で Bedrock 上のモデルを透過的に利用 |
| 外部設定 | プロンプトを SSM で管理し、コードとプロンプトを分離 |
| 限界の認識 | ツールなしでは外部情報にアクセスできない → Phase 4 への布石 |

> 💡 「たった数行でエージェントが動く。しかしこれはプロトタイプ。
> ここから本番化するために AgentCore の各コンポーネントが必要になる」
