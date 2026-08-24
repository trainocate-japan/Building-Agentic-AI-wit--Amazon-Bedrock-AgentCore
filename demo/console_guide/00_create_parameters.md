# Phase 0: SSM Parameter Store の作成（事前準備）

## 概要

システムプロンプトとモデル ID を SSM Parameter Store で管理します。
これにより、再デプロイなしでプロンプトの変更・バージョン管理が可能になります。

---

## なぜ Parameter Store を使うのか

| 観点 | コードに直書き | Parameter Store |
|:--|:--|:--|
| 変更時 | コード修正 → 再デプロイ | パラメータ変更 → エージェント再起動のみ |
| バージョン管理 | Git 履歴に依存 | 自動でバージョン番号が付与される |
| 環境差分 | if/else やファイル分割 | プレフィックスで環境分離 |
| チーム共有 | コードレビュー必須 | 権限があれば直接更新可能 |
| 監査 | Git log | CloudTrail + パラメータ履歴 |

---

## パラメータ設計

```
/agentcore/secretary-agent/
├── system-prompt    ← エージェントの人格・行動指示
└── model-id         ← 使用するモデルのID
```

> 💡 本番運用では `/agentcore/{env}/secretary-agent/` のように環境プレフィックスを追加

---

## Step 1: マネジメントコンソールで作成

### 1-1. Systems Manager コンソールを開く

1. AWS マネジメントコンソール → **Systems Manager**
2. 左ナビゲーション → **「Parameter Store」**

### 1-2. システムプロンプトの作成

1. **「Create parameter」** をクリック

2. 設定:
   | 項目 | 値 |
   |:--|:--|
   | Name | `/agentcore/secretary-agent/system-prompt` |
   | Description | `秘書エージェントのシステムプロンプト` |
   | Tier | Standard |
   | Type | String |
   | Data type | text |

3. Value に以下を入力:

```
あなたは優秀な秘書エージェントです。名前は「セクレタリー」です。

以下の方針で行動してください:
- 簡潔で正確な情報を提供する
- 日本語で応答する
- 不明な点があれば確認を取る
- ユーザーの時間を無駄にしない

あなたは研修講師の秘書として、スケジュール管理や情報収集を支援します。
```

4. **「Create parameter」** をクリック

### 1-3. モデル ID の作成

1. **「Create parameter」** をクリック

2. 設定:
   | 項目 | 値 |
   |:--|:--|
   | Name | `/agentcore/secretary-agent/model-id` |
   | Description | `使用する Bedrock モデルの ID` |
   | Tier | Standard |
   | Type | String |
   | Data type | text |

3. Value:
```
us.amazon.nova-pro-v1:0
```

4. **「Create parameter」** をクリック

---

## Step 2: AWS CLI で作成する場合

コンソール操作の代わりに CLI でも作成できます:

```bash
# システムプロンプト
aws ssm put-parameter \
    --name "/agentcore/secretary-agent/system-prompt" \
    --type "String" \
    --value "あなたは優秀な秘書エージェントです。名前は「セクレタリー」です。

以下の方針で行動してください:
- 簡潔で正確な情報を提供する
- 日本語で応答する
- 不明な点があれば確認を取る
- ユーザーの時間を無駄にしない

あなたは研修講師の秘書として、スケジュール管理や情報収集を支援します。" \
    --description "秘書エージェントのシステムプロンプト" \
    --region us-east-1

# モデル ID
aws ssm put-parameter \
    --name "/agentcore/secretary-agent/model-id" \
    --type "String" \
    --value "us.amazon.nova-pro-v1:0" \
    --description "使用する Bedrock モデルの ID" \
    --region us-east-1
```

---

## Step 3: 作成確認

```bash
# パラメータ一覧
aws ssm get-parameters-by-path \
    --path "/agentcore/secretary-agent" \
    --query "Parameters[].{Name:Name, Value:Value, Version:Version}" \
    --output table \
    --region us-east-1
```

出力例:
```
-----------------------------------------------------------------
|                        GetParametersByPath                      |
+-----------------------------------------+-------------------+--+
|                  Name                   |      Value        |V |
+-----------------------------------------+-------------------+--+
| /agentcore/secretary-agent/model-id     | us.amazon.nova... | 1|
| /agentcore/secretary-agent/system-prompt| あなたは優秀な... | 1|
+-----------------------------------------+-------------------+--+
```

---

## Step 4: バージョン管理のデモ

### 4-1. プロンプトを更新する

```bash
# バージョン2: より詳細な指示を追加
aws ssm put-parameter \
    --name "/agentcore/secretary-agent/system-prompt" \
    --type "String" \
    --value "あなたは優秀な秘書エージェントです。名前は「セクレタリー」です。

以下の方針で行動してください:
- 簡潔で正確な情報を提供する
- 日本語で応答する
- 不明な点があれば確認を取る
- ユーザーの時間を無駄にしない
- 提案をする際は必ず理由を添える
- 予定の変更時は影響範囲を確認する

あなたは研修講師の秘書として、スケジュール管理や情報収集を支援します。" \
    --overwrite \
    --region us-east-1
```

### 4-2. バージョン履歴の確認

```bash
aws ssm get-parameter-history \
    --name "/agentcore/secretary-agent/system-prompt" \
    --query "Parameters[].{Version:Version, LastModified:LastModifiedDate, Value:Value}" \
    --output table \
    --region us-east-1
```

### 4-3. 特定バージョンを取得

```bash
# バージョン1（初期版）を取得
aws ssm get-parameter \
    --name "/agentcore/secretary-agent/system-prompt:1" \
    --query "Parameter.Value" \
    --output text \
    --region us-east-1
```

> 💡 講義ポイント: 「プロンプトを変更してエージェントを再起動するだけで
> 動作が変わる。コードのデプロイは不要。問題があれば前のバージョンに戻せる」

---

## Step 5: IAM 権限の設定

エージェントの実行ロールに SSM 読み取り権限を付与します。

### 5-1. 必要な IAM ポリシー

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ssm:GetParameter",
                "ssm:GetParameters",
                "ssm:GetParametersByPath"
            ],
            "Resource": "arn:aws:ssm:us-east-1:*:parameter/agentcore/secretary-agent/*"
        }
    ]
}
```

### 5-2. AgentCore Runtime の実行ロールにアタッチ

コンソールまたは CLI:

```bash
# ポリシーを作成
aws iam create-policy \
    --policy-name AgentCoreSSMReadPolicy \
    --policy-document '{
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Action": ["ssm:GetParameter", "ssm:GetParameters", "ssm:GetParametersByPath"],
            "Resource": "arn:aws:ssm:us-east-1:*:parameter/agentcore/secretary-agent/*"
        }]
    }'

# Runtime の実行ロールにアタッチ
aws iam attach-role-policy \
    --role-name <AgentCore-Runtime-Execution-Role> \
    --policy-arn arn:aws:iam::<ACCOUNT_ID>:policy/AgentCoreSSMReadPolicy
```

---

## 講義ポイントまとめ

| トピック | 説明 |
|:--|:--|
| バージョン管理 | 変更ごとに自動でバージョン番号がインクリメント |
| ロールバック | 特定バージョンを指定して取得可能 |
| 環境分離 | パスのプレフィックスで dev/staging/prod を分離 |
| 監査 | CloudTrail でパラメータの変更履歴を追跡 |
| コスト | Standard Tier は無料（10,000パラメータまで） |

> 💡 「プロンプトエンジニアリングのイテレーションを高速に回せる。
> デプロイパイプラインを通さずに、プロンプトだけを独立して管理・更新できる」
