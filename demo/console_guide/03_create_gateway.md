# Phase 4: AgentCore Gateway の作成（Module 04 対応）

## 概要

AgentCore Gateway で Lambda ツールを MCP プロトコル経由で提供し、
エージェントから Gateway に接続してツールを自動検出・利用します。

---

## 全体の流れ

1. Lambda 関数を2つ作成（schedule / weather）
2. Gateway をコンソールで作成
3. Lambda をターゲットとして追加（tool schema 付き）
4. エージェントから Gateway 経由で接続・動作確認

---

## Step 1: Lambda 関数の作成

### 1-1. スケジュールツール Lambda

1. Lambda コンソール → **「関数の作成」**
2. 設定:
   | 項目 | 値 |
   |:--|:--|
   | 関数名 | `agentcore-schedule-tool` |
   | ランタイム | Python 3.11 |
   | アーキテクチャ | arm64 |

3. コードソース: `demo/lambda/schedule_tool/lambda_function.py` の内容を貼り付け

4. **「Deploy」** をクリック

5. テストイベントで確認:

   > 💡 **Gateway 経由の event 形式**: Gateway はツール名でルーティングするため、各 Lambda には該当ツールのパラメータだけが `input` として渡されます。Lambda 側では `event.get("name")` でツール名を確認し、`event.get("input", {})` からパラメータを取得します。

```json
{
    "name": "get_schedule",
    "input": { "date": "2026-08-05" }
}
```

### 1-2. 天気ツール Lambda

1. Lambda コンソール → **「関数の作成」**
2. 設定:
   | 項目 | 値 |
   |:--|:--|
   | 関数名 | `agentcore-weather-tool` |
   | ランタイム | Python 3.11 |
   | アーキテクチャ | arm64 |

3. コードソース: `demo/lambda/weather_tool/lambda_function.py` の内容を貼り付け

4. **「Deploy」** をクリック

5. テストイベントで確認:

   > Gateway がツール名 `get_weather` でこの Lambda にルーティングするため、Lambda は `event["input"]` から直接パラメータを取得します。

```json
{
    "name": "get_weather",
    "input": { "location": "東京" }
}
```

---

## Step 2: マネジメントコンソールで Gateway を作成

### 2-1. AgentCore Gateway コンソールを開く

1. AWS マネジメントコンソール → **Bedrock** → **AgentCore**
2. 左ナビゲーションから **「Gateways」** を選択

### 2-2. Gateway の作成

1. **「Create gateway」** をクリック

2. 基本設定:
   | 項目 | 値 |
   |:--|:--|
   | Gateway name | `secretary-agent-gateway` |
   | Description | `秘書エージェント用ツールゲートウェイ` |

3. Inbound Authorization:
   | 項目 | 値 |
   |:--|:--|
   | Authorization type | IAM |

   > IAM 認証を使うと、SigV4 で署名されたリクエストのみ受け付ける

4. **「Create gateway」** をクリック

### 2-3. Gateway URL の確認

作成後に表示される MCP エンドポイント URL を控える:
```
https://<gateway-id>.bedrock-agentcore.us-east-1.amazonaws.com/mcp
```

CLI でも確認可能:
```bash
aws bedrock-agentcore-control list-gateways \
    --query "gateways[?name=='secretary-agent-gateway'].{Id:gatewayId, Status:status}" \
    --output table --region us-east-1
```

---

## Step 3: Lambda ターゲットの追加

### 3-1. スケジュールツールターゲット

1. 作成した Gateway をクリック
2. **「Targets」** タブ → **「Add target」**

3. 設定:
   | 項目 | 値 |
   |:--|:--|
   | Target type | Lambda function |
   | Name | `schedule-tool` |
   | Lambda function ARN | `arn:aws:lambda:us-east-1:<ACCOUNT>:function:agentcore-schedule-tool` |

4. Tool Schema（`demo/lambda/tool_schemas/schedule_tools.json` の内容）:
```json
[
  {
    "name": "get_schedule",
    "description": "山下光洋のスケジュール（セミナー登壇、勉強会、コース実施など）を取得します。日付を指定すると該当日のみ、指定しないと直近の全件を返します。",
    "inputSchema": {
      "type": "object",
      "description": "スケジュール取得のパラメータ",
      "properties": {
        "date": {
          "type": "string",
          "description": "日付（YYYY-MM-DD形式）。省略すると直近の全スケジュールを返す"
        }
      },
      "required": []
    }
  }
]
```

5. Credential provider: **Gateway IAM Role**
6. **「Add target」** をクリック

### 3-2. 天気ツールターゲット

1. **「Add target」** をクリック

2. 設定:
   | 項目 | 値 |
   |:--|:--|
   | Target type | Lambda function |
   | Name | `weather-tool` |
   | Lambda function ARN | `arn:aws:lambda:us-east-1:<ACCOUNT>:function:agentcore-weather-tool` |

3. Tool Schema（`demo/lambda/tool_schemas/weather_tools.json` の内容）:
```json
[
  {
    "name": "get_weather",
    "description": "指定した場所（都市名）の現在の天気情報を取得します。気温、天候、湿度、風の情報を返します。",
    "inputSchema": {
      "type": "object",
      "description": "天気情報取得のパラメータ",
      "properties": {
        "location": {
          "type": "string",
          "description": "場所の名前（都市名、例: 東京、大阪、札幌）"
        }
      },
      "required": ["location"]
    }
  }
]
```

4. Credential provider: **Gateway IAM Role**
5. **「Add target」** をクリック

---

## Step 4: IAM 権限の確認

Gateway が Lambda を invoke できるようにするため、Gateway の IAM ロールに権限が必要です。
コンソールから作成した場合は自動で設定されますが、確認:

```bash
# Gateway のロールを確認
aws iam list-roles \
    --query "Roles[?contains(RoleName, 'AgentCore') && contains(RoleName, 'Gateway')]" \
    --output table
```

また、ローカルから Gateway にアクセスするユーザー/ロールには以下が必要:

```json
{
    "Effect": "Allow",
    "Action": "bedrock-agentcore:InvokeGateway",
    "Resource": "arn:aws:bedrock-agentcore:us-east-1:<ACCOUNT>:gateway/<GATEWAY_ID>"
}
```

---

## Step 5: エージェントから Gateway 経由で接続

### 5-1. 環境変数を設定

```bash
export GATEWAY_URL="https://<gateway-id>.bedrock-agentcore.us-east-1.amazonaws.com/mcp"
```

### 5-2. 追加パッケージインストール

```bash
pip install mcp-proxy-for-aws
```

### 5-3. Gateway 版エージェントを起動

```bash
cd demo/src
python -u agent_with_gateway.py
```

起動時の出力例:
```
📌 設定を読み込み中...
   Model: us.amazon.nova-pro-v1:0
   Gateway: https://xxxxxxxx.bedrock-agentcore.us-east-1.amazonaws.com/mcp

============================================================
🤖 Secretary Agent - Phase 4 (AgentCore Gateway)
   AgentCore 研修デモ: Gateway 経由ツール利用版
============================================================

📡 Gateway に接続中...
   ✅ 接続成功！ 2 個のツールを検出:
      - get_schedule: 山下光洋のスケジュール（セミナー登壇、勉強会...
      - get_weather: 指定した場所（都市名）の現在の天気情報を取得...
```

### 5-4. デモ対話

```
👤 You: 今日のスケジュールを教えて
🤖 Secretary: [Gateway → Lambda → get_schedule 実行]
   📅 2026-08-05 のスケジュール:
     09:00 - Building Agentic AI with Amazon Bedrock AgentCore (480min)

👤 You: 東京の天気は？
🤖 Secretary: [Gateway → Lambda → get_weather 実行]
   🌤️ 東京の天気情報:
     気温: 33℃、天候: 晴れ、湿度: 65%、風: 南 3m/s
```

---

## 講義ポイントまとめ

| トピック | 説明 |
|:--|:--|
| ツール分離 | エージェントのコードとツールの実装が完全に分離 |
| 自動検出 | `tools/list` でツールを自動ディスカバリ（コード変更不要で拡張） |
| Lambda ターゲット | サーバーレスでスケーラブルなツール実装 |
| IAM 認証 | SigV4 で Gateway へのアクセスを制御 |
| MCP 準拠 | 標準プロトコルでフレームワーク非依存 |

### デモで見せるべきポイント

1. **ツール自動検出**: Gateway にツールを追加するだけでエージェントが自動で使える
2. **コード変更不要**: Lambda を追加/変更してもエージェント側のコードは変わらない
3. **認証の一元化**: 個々の API に認証コードを書かずに Gateway が一括管理

### Gateway → Lambda の event 形式

Gateway はツール名（Target Name）でルーティングを行い、対応する Lambda を invoke します。
Lambda が受け取る event の構造:

```json
{
    "name": "get_schedule",
    "input": {
        "date": "2026-08-05"
    }
}
```

| フィールド | 説明 |
|:--|:--|
| `name` | Gateway が呼び出したツール名（Target のスキーマで定義） |
| `input` | エージェントが渡したツールパラメータ（inputSchema に従う） |

Lambda のレスポンス形式:
```json
{
    "output": "結果のテキスト"
}
```

> 💡 「Gateway がツール名でルーティングするので、1 Lambda = 1 ツールの設計であれば
> Lambda 側のディスパッチロジックは最小限で済む」
