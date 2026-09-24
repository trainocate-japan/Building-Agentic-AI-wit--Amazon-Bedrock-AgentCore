# AgentCore Observability 権限分離 設計メモ

> 対象: AgentCore Observability を使うシステム運用者側の権限分離
> 目的: 「パワーユーザーはユーザー入力（個人情報を含む）まで閲覧可」「監視オペレーターはエラー・性能のみ、入力情報は非表示」を実現する

---

## 1. 前提: スパンの実体は CloudWatch Logs

AgentCore Observability はエージェントの実行情報を Amazon CloudWatch に集約する。データの実体は **CloudWatch Logs のロググループ / ログストリーム**であり、それを CloudWatch Transaction Search / GenAI Observability がトレースとして可視化する。

| データ種別 | 格納先 | 主な内容 |
|---|---|---|
| 標準ログ (stdout/stderr) | `/aws/bedrock-agentcore/runtimes/<agent_id>-<endpoint_name>/[runtime-logs]` | ランタイムエラー、アプリログ |
| OTEL 構造化ログ | `.../otel-rt-logs` | 実行詳細、エラー追跡、性能データ |
| トレース / スパン | ロググループ内の `spans` ログストリーム（または共有 `aws/spans` ロググループの `default` ストリーム） | エージェント実行系列、**LLM 呼び出しと応答**、**ツール入出力**、エラーパス |
| メトリクス | 名前空間 `bedrock-agentcore`（EMF） | レイテンシ、実行時間、トークン使用量、エラー率 |

**重要**: ユーザー入力（個人情報を含みうる）や LLM 応答・ツール入出力は「スパン属性」として `spans` ログストリームに載る（Unified telemetry の場合）。したがって権限分離は **CloudWatch Logs レイヤー**に対して行うのが基本方針となる。

### テレメトリ配信モード（保存先が変わる点に注意）

- **Unified telemetry**（推奨 / 2026-07-20 以降作成のエージェントの既定）: ペイロード属性はスパン上に残り、すべて 1 つのロググループの `spans` ストリームへ。制御対象が 1 箇所で済む。
- **Split telemetry**（それ以前の既定）: ADOT が大きなペイロード属性をスパンから切り離し、`otel-rt-logs` の event record（`body.input.messages` / `body.output.messages` など）へ送る。スパン本体は共有 `aws/spans` ロググループへ。**入力情報を隠すには event record 側のロググループにもポリシー適用が必要**。
- AgentCore Runtime では環境変数 `UNIFIED_TRACES_DESTINATION_ENABLED` で切替（`true`=Unified / `false`=Split）。

出典:
- [View observability data for your Amazon Bedrock AgentCore agents](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-view.html)
- [Telemetry setup and delivery](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/supported-frameworks-telemetry.html)

---

## 2. 要件と役割マッピング

| 役割 | 見せたいもの | 見せたくないもの |
|---|---|---|
| パワーユーザー | エラー・性能に加え、**ユーザー入力の生データ**（説明可能性のため） | ― |
| 監視オペレーター | エラー状況、性能（レイテンシ・速度など） | **ユーザー入力（個人情報）** |

---

## 3. アプローチ A: データ保護ポリシー（マスキング）+ `logs:Unmask`（推奨）

同じダッシュボード・同じトレース画面を両者が使いつつ、個人情報部分だけを役割でマスク/非マスク切替できる。要件に最も素直に合致する。

- スパンのロググループに**データ保護ポリシー**を設定 → 個人情報を取り込み時に自動検出・マスク（既定は `****` 表示）
- **`logs:Unmask` を持つ人だけ**が Logs Insights の `unmask` コマンドや `GetLogEvents`(unmask=true) で生データを閲覧できる

| 役割 | `logs:Unmask` | 結果 |
|---|---|---|
| パワーユーザー | 許可 | 入力の生データまで閲覧可 |
| 監視オペレーター | 付与しない / 明示 Deny | エラー・性能は見えるが個人情報はマスク |

### 3-1. データ保護ポリシーの書き方

必ず **2 つの Statement ブロック**で構成する。両ブロックの `DataIdentifier` 配列は**完全一致**が必須。

- Audit ブロック: 検出する機密データ種別（`DataIdentifier`）＋ `FindingsDestination`
- Deidentify ブロック: 実際のマスク。`"MaskConfig": {}` は**空オブジェクト必須**

```json
{
  "Name": "agentcore-span-pii-protection",
  "Description": "Mask PII in AgentCore agent spans",
  "Version": "2021-06-01",
  "Statement": [
    {
      "Sid": "audit-pii",
      "DataIdentifier": [
        "arn:aws:dataprotection::aws:data-identifier/EmailAddress",
        "arn:aws:dataprotection::aws:data-identifier/Name",
        "arn:aws:dataprotection::aws:data-identifier/Address",
        "arn:aws:dataprotection::aws:data-identifier/PhoneNumber-JP"
      ],
      "Operation": {
        "Audit": { "FindingsDestination": {} }
      }
    },
    {
      "Sid": "mask-pii",
      "DataIdentifier": [
        "arn:aws:dataprotection::aws:data-identifier/EmailAddress",
        "arn:aws:dataprotection::aws:data-identifier/Name",
        "arn:aws:dataprotection::aws:data-identifier/Address",
        "arn:aws:dataprotection::aws:data-identifier/PhoneNumber-JP"
      ],
      "Operation": {
        "Deidentify": { "MaskConfig": {} }
      }
    }
  ]
}
```

特定ロググループに適用（CLI）:

```bash
aws logs put-data-protection-policy \
  --log-group-identifier "/aws/bedrock-agentcore/runtimes/<agent_id>-<endpoint_name>" \
  --policy-document file://agentcore-dpp.json
```

複数エージェントへ一括適用（アカウントポリシー / プレフィックスで絞り込み）:

```bash
aws logs put-account-policy \
  --policy-name "agentcore-pii-protection" \
  --policy-type "DATA_PROTECTION_POLICY" \
  --policy-document file://agentcore-dpp.json \
  --scope "ALL" \
  --selection-criteria "LogGroupNamePrefix:/aws/bedrock-agentcore/runtimes/"
```

ロググループ個別ポリシーとアカウントポリシーが両方ある場合は**累積**（いずれかで指定された語がマスクされる）。

### 3-2. カスタムデータ識別子（業務固有の番号など）

マネージド識別子（100 種類以上）でカバーできない会員番号・社内 ID などは正規表現で定義する。ポリシードキュメント直下に `Configuration.CustomDataIdentifier` を置き、Audit / Deidentify の `DataIdentifier` からは `Name` で参照する。

```json
"Configuration": {
  "CustomDataIdentifier": [
    { "Name": "MemberId", "Regex": "M\\d{8}" }
  ]
}
```

### 3-3. オペレーターへの明示 Deny（SCP / IAM）

```json
{
  "Sid": "RestrictUnmasking",
  "Effect": "Deny",
  "Action": "logs:Unmask",
  "Resource": "arn:aws:logs:*:ACCOUNT_ID:log-group:/aws/bedrock-agentcore/runtimes/*:*",
  "Condition": {
    "StringEquals": { "aws:PrincipalArn": "arn:aws:iam::ACCOUNT_ID:role/MonitoringOperatorRole" }
  }
}
```

出典:
- [PutDataProtectionPolicy API リファレンス（JSON 例）](https://docs.aws.amazon.com/AmazonCloudWatchLogs/latest/APIReference/API_PutDataProtectionPolicy.html)
- [Protect sensitive log data with masking（マスク可能なデータ種別一覧）](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/mask-sensitive-log-data.html)
- [Detect and protect sensitive data with Amazon Lex and CloudWatch Logs（Unmask 制限 SCP 例・カスタム識別子）](https://aws.amazon.com/blogs/machine-learning/detect-and-protect-sensitive-data-with-amazon-lex-and-amazon-cloudwatch-logs/)

---

## 4. アプローチ B: IAM でアクセス対象そのものを分離

情報源のレベルで分ける。マスキング（A）と併用すると実運用で扱いやすい。

- **オペレーター**: CloudWatch メトリクス・アラーム・ダッシュボード（レイテンシ・エラー率・トークン数など）への読み取りのみ。スパンのロググループへの `logs:GetLogEvents` / `logs:StartQuery` は付与しない。
- **パワーユーザー**: 上記に加え、スパンのロググループ（`/aws/bedrock-agentcore/runtimes/*`）と Transaction Search でのトレース詳細閲覧を許可。

メトリクスには個人情報が含まれないため、オペレーターは性能・エラー監視を継続できる。ただし単独ではエラースパンの詳細追跡がしにくくなるため A との併用を推奨。

---

## 5. アプローチ C: そもそも入力コンテンツを記録させない（オプトアウト）

個人情報をスパンに一切残したくない場合、AgentCore の環境変数で入出力コンテンツ抽出を停止できる。

```
AWS_GENAI_CONTENT_EXTRACTION_OPT_OUT=true
```

ただし本要件では「パワーユーザーは入力を見たい」ため**全体オプトアウトは不適**。A のマスキングの方が要件に合う。

出典:
- [Send AI agent telemetry（`AWS_GENAI_CONTENT_EXTRACTION_OPT_OUT`）](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/omni-send-ai-agent-telemetry.html)

---

## 6. 追加要件: メッセージをまるごと特定対象者に非表示にする設計

「フィールド単位のマスク」ではなく「メッセージ（入力/出力の会話コンテンツ）そのものを、特定の対象者には一切見せない」を実現する設計オプション。

### 6-A. マスキングを"メッセージ全体"に効かせる

データ保護ポリシーはフィールド単位の識別子でマスクするのが基本だが、**カスタムデータ識別子の正規表現を会話コンテンツ全体にマッチさせる**ことで、実質的にメッセージ本文を丸ごとマスクできる。

- Split telemetry なら会話本文は event record の `body.input.messages` / `body.output.messages` に入るため、その値にマッチする正規表現を定義。
- Unified telemetry ならスパン属性側の会話テキストを対象にする。
- 見てよい対象者（パワーユーザー）にだけ `logs:Unmask` を付与する構図は A と同じ。

留意: 正規表現で「本文全体」を確実に捕捉するのは難しく、取りこぼしリスクがある。より確実なのは 6-B / 6-C の"物理分離"アプローチ。

### 6-B. 会話コンテンツを別ロググループに分離し、ロググループ単位で IAM 制御（推奨）

最も確実。会話本文（メッセージ）と、性能・エラー系の情報を**別々のロググループに物理的に分ける**。

- **Split telemetry を採用**すると、会話ペイロードは event record として `otel-rt-logs` 側へ、スパン骨格（メタデータ・レイテンシ・エラー）は `aws/spans` 側へ分かれる。
- ロググループ単位で IAM を設計する:
  - 監視オペレーター: `aws/spans`（性能・エラー）のみ `logs:GetLogEvents` / `logs:StartQuery` を許可。会話ペイロードのロググループ（`otel-rt-logs`）へのアクセスは付与しない/明示 Deny。
  - パワーユーザー: 両方のロググループを許可。
- Unified telemetry は 1 ロググループに集約されるため物理分離しにくい。この要件を重視するなら Split telemetry を選ぶ判断もあり得る（評価・可観測性の利便性とのトレードオフ）。

オペレーターへの明示 Deny 例（会話ペイロードのロググループを閉じる）:

```json
{
  "Sid": "DenyConversationLogs",
  "Effect": "Deny",
  "Action": ["logs:GetLogEvents", "logs:FilterLogEvents", "logs:StartQuery", "logs:GetLogRecord"],
  "Resource": "arn:aws:logs:*:ACCOUNT_ID:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*otel-rt-logs*",
  "Condition": {
    "StringEquals": { "aws:PrincipalArn": "arn:aws:iam::ACCOUNT_ID:role/MonitoringOperatorRole" }
  }
}
```

### 6-C. サブスクリプションフィルタで"見せてよい情報だけ"を別ロググループへ複製

元のロググループはパワーユーザー限定にし、オペレーター向けには**性能・エラーだけを抽出した派生ロググループ**を用意する。

- サブスクリプションフィルタ（ロググループ単位、またはアカウントレベル）で、フィルタパターンにマッチした（＝会話本文を含まない、エラー/メトリクス系の）ログのみを Lambda / Firehose / Kinesis Data Streams 経由でオペレーター用ロググループへ配信。
- オペレーターはその派生ロググループだけを閲覧。元のロググループにはアクセスさせない。
- アカウントレベルでは `selection-criteria`（`NOT IN`）で無限ループ対象を除外する点に注意。

留意: フィルタパターン設計を誤ると会話本文が派生側に混入するため、"許可リスト"方式（性能・エラーの構造化フィールドだけ通す）で設計する。

#### 構成イメージ

```
[元ロググループ: 会話本文含む全スパン/ログ]  ← パワーユーザーのみアクセス可
        │
        │ サブスクリプションフィルタ（filterPattern で「性能・エラー系」だけ抽出）
        ▼
[Lambda / Firehose / Kinesis で整形（会話本文フィールドを落とす）]
        ▼
[派生ロググループ: 性能・エラーのみ]          ← 監視オペレーターが閲覧
```

#### Step 1: フィルタパターン設計（許可リスト方式）

CloudWatch Logs のフィルタパターンは JSON プロパティセレクタで条件を書ける。「本文フィールドが存在しないもの」を除外するより、「見せてよいフィールドが存在するもの」を通す発想で設計する。

- エラーのみ通す例（`level` が ERROR のイベント）:

  ```
  { $.level = "ERROR" }
  ```

- 会話本文フィールドを含むイベントを除外する例（`NOT EXISTS` を利用）:

  ```
  { $.body.input.messages NOT EXISTS && $.body.output.messages NOT EXISTS }
  ```

  注: サポートされる変数は `NOT EXISTS`。`IS NOT` と `EXISTS` は未サポート。

ただしフィルタパターンは「そのイベントを配信するか否か」の判定のみで、**フィールドの削除まではできない**。本文フィールドを確実に落とすには Step 2 の変換を併用する。

#### Step 2: 配信先で整形（会話本文を物理的に落とす）

サブスクリプションフィルタの配信先を Lambda にして、そこで会話本文フィールド（`body.input.messages` / `body.output.messages` など）を除去し、レイテンシ・トークン数・エラー内容など許可フィールドだけを派生ロググループへ `PutLogEvents` する。Firehose なら変換 Lambda を挟む。

擬似コード（配信先 Lambda）:

```python
import base64, gzip, json, boto3

logs = boto3.client("logs")
ALLOWED = {"traceId", "spanId", "name", "level", "durationMs",
           "http.status_code", "error", "gen_ai.usage.total_tokens"}

def handler(event, _ctx):
    payload = json.loads(gzip.decompress(base64.b64decode(event["awslogs"]["data"])))
    events = []
    for e in payload["logEvents"]:
        try:
            rec = json.loads(e["message"])
        except json.JSONDecodeError:
            continue  # 非JSONは会話本文の混入リスクがあるため落とす
        # 許可リストのフィールドだけ残す（会話本文は転記しない）
        safe = {k: v for k, v in rec.items() if k in ALLOWED}
        events.append({"timestamp": e["timestamp"], "message": json.dumps(safe)})
    if events:
        logs.put_log_events(
            logGroupName="/observability/operator-view",
            logStreamName=payload["logStream"],
            logEvents=events,
        )
```

ポイント: **拒否リストではなく許可リスト**で書く。新しい属性が将来追加されても、許可リストにない限り派生側へ漏れない。

#### Step 3-a: ロググループ単位サブスクリプションフィルタ（PutSubscriptionFilter）

```bash
aws logs put-subscription-filter \
  --log-group-name "/aws/bedrock-agentcore/runtimes/<agent_id>-<endpoint_name>" \
  --filter-name "operator-view-safe-only" \
  --filter-pattern '{ $.body.input.messages NOT EXISTS && $.body.output.messages NOT EXISTS }' \
  --destination-arn "arn:aws:lambda:<region>:<ACCOUNT_ID>:function:RedactAndForward"
```

Lambda 以外（Kinesis / Firehose）を宛先にする場合は、CloudWatch Logs が宛先へ書き込むための `--role-arn` が必要。Lambda 宛先では不要（Lambda 側のリソースポリシーで許可）。

#### Step 3-b: アカウントレベルで複数エージェントに一括適用（PutAccountPolicy）

```bash
aws logs put-account-policy \
  --policy-name "operator-view-safe-only" \
  --policy-type "SUBSCRIPTION_FILTER_POLICY" \
  --policy-document '{"DestinationArn":"arn:aws:lambda:<region>:<ACCOUNT_ID>:function:RedactAndForward","FilterPattern":"{ $.body.input.messages NOT EXISTS && $.body.output.messages NOT EXISTS }"}' \
  --selection-criteria 'LogGroupName NOT IN ["/observability/operator-view"]' \
  --scope "ALL"
```

- `selection-criteria` は**無限ループ防止に必須**。派生ロググループ（`/observability/operator-view`）自身を必ず除外する。除外しないと派生ログが再びフィルタ対象になり再帰する。
- `selection-criteria` で現在サポートされる演算子は `NOT IN` のみ。
- アカウントレベルのサブスクリプションフィルタポリシーは **1 アカウントにつき 1 つ**。

#### Step 4: IAM で閲覧範囲を分離

- 監視オペレーター: 派生ロググループ `/observability/operator-view` のみ `logs:GetLogEvents` / `logs:StartQuery` を許可。元ロググループ（`/aws/bedrock-agentcore/runtimes/*`）は付与しない/明示 Deny。
- パワーユーザー: 元ロググループを許可（会話本文まで閲覧可）。

```json
{
  "Sid": "OperatorReadDerivedOnly",
  "Effect": "Allow",
  "Action": ["logs:GetLogEvents", "logs:FilterLogEvents", "logs:StartQuery", "logs:GetQueryResults"],
  "Resource": "arn:aws:logs:*:ACCOUNT_ID:log-group:/observability/operator-view:*"
}
```

#### この方式の評価

- 長所: オペレーターは元ロググループに触れないため、会話本文の混入リスクを IAM 境界で断てる（マスク取りこぼしに依存しない）。ダッシュボード/クエリもオペレーター専用に最適化できる。
- 短所: 派生パイプライン（Lambda/Firehose）の運用・コストが増える。ほぼリアルタイムだが元データとの間に配信遅延がある。整形ロジックの許可リスト保守が必要。

出典:
- [Telemetry setup and delivery（Split telemetry / event records / `body.input.messages`）](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/supported-frameworks-telemetry.html)
- [Subscription filters — Concepts](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/subscription-concepts.html)
- [Create an account-level subscription filter policy](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/CreateSubscriptionFilter-Account.html)
- [PutSubscriptionFilter API リファレンス](https://docs.aws.amazon.com/AmazonCloudWatchLogs/latest/APIReference/API_PutSubscriptionFilter.html)
- [Filter pattern syntax（NOT EXISTS 等）](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/FilterAndPatternSyntax.html)

---

## 7. 推奨構成まとめ

| 目的 | 推奨アプローチ |
|---|---|
| 個人情報「フィールド」を役割で出し分け（同一画面共有） | **A**（データ保護ポリシー + `logs:Unmask`） |
| 情報源レベルの分離を追加したい | A + **B** |
| メッセージ「本文まるごと」を特定対象者に非表示 | **6-B**（Split telemetry + ロググループ単位 IAM）を軸に、必要なら **6-C** で派生ロググループを提供 |
| 個人情報を一切記録したくない（説明可能性を捨てる） | **C**（オプトアウト） |

### 実装上の共通注意点

- マスク判定は**取り込み時（ingest）**に行われる。ポリシー設定より前に取り込まれたログは遡ってマスクされない。**運用開始前に設定**すること。
- アカウント全体ポリシーは既存ロググループにも適用されるが、反映まで最大 5 分程度（結果整合性）。
- テレメトリ配信モード（Unified / Split）で会話本文の格納先が変わる。**どのロググループ/ログストリームに個人情報が載るか**を確認してからポリシー/権限を設計する。

---

## 出典一覧

- View observability data for your Amazon Bedrock AgentCore agents — https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-view.html
- Telemetry setup and delivery — https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/supported-frameworks-telemetry.html
- Send AI agent telemetry — https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/omni-send-ai-agent-telemetry.html
- PutDataProtectionPolicy API リファレンス — https://docs.aws.amazon.com/AmazonCloudWatchLogs/latest/APIReference/API_PutDataProtectionPolicy.html
- Protect sensitive log data with masking — https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/mask-sensitive-log-data.html
- Detect and protect sensitive data with Amazon Lex and CloudWatch Logs — https://aws.amazon.com/blogs/machine-learning/detect-and-protect-sensitive-data-with-amazon-lex-and-amazon-cloudwatch-logs/
- Subscription filters — Concepts — https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/subscription-concepts.html
- Create an account-level subscription filter policy — https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/CreateSubscriptionFilter-Account.html
- PutSubscriptionFilter API リファレンス — https://docs.aws.amazon.com/AmazonCloudWatchLogs/latest/APIReference/API_PutSubscriptionFilter.html
- Filter pattern syntax for metric filters, subscription filters, filter log events, and Live Tail — https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/FilterAndPatternSyntax.html

> 注: 一部の内容はライセンス配慮のため出典を要約・言い換えのうえ記載しています。
