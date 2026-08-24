# Amazon Bedrock AgentCore Code Interpreter 使い方ガイド

## Code Interpreter とは

AgentCore Code Interpreter は、AIエージェントがコードを**安全なサンドボックス環境**で実行するためのフルマネージドサービスです。エージェントが生成したコードを隔離された環境で実行し、データ分析・数値計算・可視化・ファイル処理などを行えます。

### 主な特徴

- **セキュアなサンドボックス**: コンテナ化された隔離環境でコードを実行
- **複数言語対応**: Python、JavaScript、TypeScript をサポート
- **大規模データ処理**: S3上のGBスケールデータを直接参照・処理可能
- **長時間実行**: デフォルト15分、最大8時間のセッションタイムアウト
- **豊富なプリインストールライブラリ**: pandas, numpy, matplotlib, scikit-learn, PyTorch 等
- **VPC対応**: プライベートネットワーク内のリソースにアクセス可能
- **ファイルシステムマウント**: S3 Files / EFS をセッションにマウント

---

## サポートされるランタイム

### Python ランタイム

主要なプリインストールライブラリ：

| カテゴリ | ライブラリ |
|---|---|
| データ分析 | pandas, polars, numpy, scipy, statsmodels |
| 可視化 | matplotlib, seaborn, plotly, bokeh |
| 機械学習 | scikit-learn, torch, torchvision, xgboost, spacy |
| 数学/最適化 | sympy, cvxpy, ortools, pulp, z3-solver |
| Web/API | requests, beautifulsoup4, fastapi, Flask, Django |
| クラウド/DB | boto3, duckdb, SQLAlchemy, pymongo, redis, psycopg2 |
| ファイル処理 | openpyxl, PyPDF2, pdfplumber, python-docx |
| 画像/動画 | pillow, opencv-python, moviepy, ffmpeg-python |

### Node.js ランタイム (JavaScript / TypeScript)

| パッケージ | 説明 |
|---|---|
| `axios` | HTTP クライアント |
| `lodash` | ユーティリティライブラリ |
| `uuid` | UUID 生成 |
| `zod` | スキーマバリデーション |
| `cheerio` | HTML パース |

---

## ネットワークモード

Code Interpreter は2つのネットワークモードを提供します：

| モード | 説明 | ユースケース |
|---|---|---|
| **PUBLIC** | インターネットアクセス可能（デフォルト） | 外部API呼び出し、パッケージインストール |
| **VPC** | 指定VPC内で実行 | プライベートDB/内部API/S3 Files/EFSへのアクセス |

---

## コードサンプル

### 1. SDK Client を使ったシンプルな実行

```python
from bedrock_agentcore.tools.code_interpreter_client import CodeInterpreter
import json

# Code Interpreter クライアントを初期化
code_client = CodeInterpreter('us-west-2')

# セッションを開始
code_client.start()

try:
    # Python コードを実行
    response = code_client.invoke("executeCode", {
        "language": "python",
        "code": 'print("Hello World!!!")'
    })

    # レスポンスを表示
    for event in response["stream"]:
        print(json.dumps(event["result"], indent=2))

finally:
    # セッションをクリーンアップ
    code_client.stop()
```

### 2. code_session コンテキストマネージャを使う例

```python
from bedrock_agentcore.tools.code_interpreter_client import code_session
import json

with code_session("us-west-2") as code_client:
    response = code_client.invoke("executeCode", {
        "code": """
import pandas as pd
import numpy as np

# サンプルデータ作成
df = pd.DataFrame({
    'name': ['Alice', 'Bob', 'Charlie'],
    'score': [85, 92, 78]
})
print(df.describe())
""",
        "language": "python",
        "clearContext": False
    })

    for event in response["stream"]:
        print(json.dumps(event["result"], indent=2))
```

### 3. Boto3 を使った直接実行

```python
import boto3
import json

client = boto3.client("bedrock-agentcore", region_name="us-west-2")

# セッション開始
session_response = client.start_code_interpreter_session(
    codeInterpreterIdentifier="aws.codeinterpreter.v1",
    name="my-code-session",
    sessionTimeoutSeconds=900
)
session_id = session_response["sessionId"]
print(f"Started session: {session_id}")

try:
    # コード実行
    execute_response = client.invoke_code_interpreter(
        codeInterpreterIdentifier="aws.codeinterpreter.v1",
        sessionId=session_id,
        name="executeCode",
        arguments={
            "language": "python",
            "code": "print('Hello from Boto3!')"
        }
    )

    # ストリームからテキスト出力を取得
    for event in execute_response['stream']:
        if 'result' in event:
            result = event['result']
            if 'content' in result:
                for content_item in result['content']:
                    if content_item['type'] == 'text':
                        print(content_item['text'])

finally:
    # セッション停止
    client.stop_code_interpreter_session(
        codeInterpreterIdentifier="aws.codeinterpreter.v1",
        sessionId=session_id
    )
    print(f"Stopped session: {session_id}")
```

### 4. Strands Agents との統合

```python
from strands import Agent
from strands_tools.code_interpreter import AgentCoreCodeInterpreter

# Code Interpreter ツールを初期化
code_interpreter_tool = AgentCoreCodeInterpreter(region="us-west-2")

# システムプロンプトでエージェントの動作を定義
SYSTEM_PROMPT = """You are an AI assistant that validates answers through code execution.
When asked about code, algorithms, or calculations, write Python code to verify your answers."""

# エージェントを作成
agent = Agent(
    tools=[code_interpreter_tool.code_interpreter],
    system_prompt=SYSTEM_PROMPT
)

# エージェントにタスクを依頼
prompt = "フィボナッチ数列の最初の10項を計算してください。"
response = agent(prompt)
print(response.message["content"][0]["text"])
```

### 5. LangChain との統合

```python
import json
from bedrock_agentcore.tools.code_interpreter_client import code_session
from langchain.agents import create_tool_calling_agent, AgentExecutor, tool
from langchain_aws import ChatBedrockConverse
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# Code Interpreter ツールを定義
@tool
def execute_python(code: str, description: str = "") -> str:
    """Execute Python code"""
    if description:
        code = f"# {description}\n{code}"

    print(f"\nGenerated Code: \n{code}")

    with code_session("us-west-2") as code_client:
        response = code_client.invoke("executeCode", {
            "code": code,
            "language": "python",
            "clearContext": False
        })
        for event in response["stream"]:
            return json.dumps(event["result"])

# LLM を初期化
llm = ChatBedrockConverse(
    model_id="anthropic.claude-sonnet-4-20250514-v1:0",
    region_name="us-west-2"
)

# プロンプトテンプレート
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful AI assistant that validates all answers through code execution."),
    MessagesPlaceholder("chat_history", optional=True),
    ("human", "{input}"),
    MessagesPlaceholder("agent_scratchpad"),
])

# エージェントを作成・実行
agent = create_tool_calling_agent(llm, [execute_python], prompt)
agent_executor = AgentExecutor(agent=agent, tools=[execute_python], verbose=True)
result = agent_executor.invoke({"input": "Calculate pi to 100 decimal places"})
```

### 6. TypeScript SDK (Strands)

```typescript
import { CodeInterpreterTools } from 'bedrock-agentcore/experimental/code-interpreter/strands'
import { Agent, BedrockModel } from '@strands-agents/sdk'

// Code Interpreter ツールを作成
const codeInterpreter = new CodeInterpreterTools({ region: 'us-west-2' })

// セッション開始
await codeInterpreter.startSession()

// エージェントを作成
const agent = new Agent({
  model: new BedrockModel({ modelId: 'anthropic.claude-sonnet-4-20250514-v1:0' }),
  tools: codeInterpreter.tools,
})

// エージェントを実行
const response = await agent.invoke('Calculate the factorial of 20')
console.log(response)

// セッション停止
await codeInterpreter.stopSession()
```

### 7. TypeScript SDK (Vercel AI SDK)

```typescript
import { createExecuteCodeTool } from 'bedrock-agentcore/code-interpreter/vercel-ai'
import { CodeInterpreter } from 'bedrock-agentcore/code-interpreter'

const interpreter = new CodeInterpreter({ region: 'us-west-2' })
const executeCodeTool = createExecuteCodeTool(interpreter)

// Vercel AI SDK エージェントと組み合わせ
const agent = new ToolLoopAgent({
  model: bedrock('global.anthropic.claude-sonnet-4-20250514-v1:0'),
  tools: { executeCode: executeCodeTool }
})
```

---

## VPC 内での利用

VPC モードでは、Code Interpreter がプライベートサブネット内で実行され、内部リソースにアクセスできます。

### コンソールでの設定手順

1. AgentCore コンソール → **Built-in Tools** → **Code Interpreter**
2. **Create Code Interpreter** を選択
3. ネットワーク設定で **VPC** を選択
4. VPC、サブネット（NATゲートウェイ付きプライベートサブネット推奨）、セキュリティグループを選択
5. 実行ロールを設定

### Boto3 でカスタム Code Interpreter (VPC モード) を作成

```python
import boto3

cp_client = boto3.client(
    'bedrock-agentcore-control',
    region_name='us-west-2'
)

response = cp_client.create_code_interpreter(
    name="myVpcCodeInterpreter",
    description="VPC内のデータベースにアクセス可能なCode Interpreter",
    executionRoleArn="arn:aws:iam::123456789012:role/my-execution-role",
    networkConfiguration={
        'networkMode': 'VPC',
        'networkModeConfig': {
            'subnets': ['subnet-0123456789abcdef0', 'subnet-0123456789abcdef1'],
            'securityGroups': ['sg-0123456789abcdef0']
        }
    }
)

code_interpreter_id = response["codeInterpreterId"]
print(f"Code Interpreter ID: {code_interpreter_id}")
```

### PUBLIC モードで作成する場合

```python
response = cp_client.create_code_interpreter(
    name="myPublicCodeInterpreter",
    description="インターネットアクセス可能なCode Interpreter",
    executionRoleArn="arn:aws:iam::123456789012:role/my-execution-role",
    networkConfiguration={
        "networkMode": "PUBLIC"
    }
)
```

### CDK での VPC 設定例

```python
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_bedrockagentcore as agentcore

code_interpreter = agentcore.CodeInterpreterCustom(self, "MyCodeInterpreter",
    code_interpreter_custom_name="my_sandbox_interpreter",
    description="Code interpreter with isolated network access",
    network_configuration=agentcore.BrowserNetworkConfiguration.using_vpc(self,
        vpc=ec2.Vpc(self, "VPC", restrict_default_security_group=False)
    )
)
```

---

## S3 / EFS ファイルシステムのマウント

Code Interpreter のセッションに S3 Files または EFS をマウントして、大規模データを直接処理できます。

### ストレージオプション比較

| タイプ | 永続性 | VPC必須 | 最適なユースケース |
|---|---|---|---|
| **S3 Files** | S3バケットと双方向同期 | Yes | データセット、S3 API とファイル操作の両方が必要 |
| **Amazon EFS** | 削除するまで永続 | Yes | 共有リファレンスデータ、セッション間の読み書き共有 |

### S3 Files マウントの設定

```python
import boto3

# コントロールプレーン: Code Interpreter 作成時にマウント設定
cp = boto3.client("bedrock-agentcore-control", region_name="us-west-2")

response = cp.create_code_interpreter(
    name="data-code-interpreter",
    executionRoleArn="arn:aws:iam::<account-id>:role/CodeInterpreterExecutionRole",
    networkConfiguration={
        "networkMode": "VPC",
        "vpcConfig": {
            "subnets": ["subnet-xxx", "subnet-yyy"],
            "securityGroups": ["sg-xxx"]
        }
    },
    filesystemConfigurations=[
        {
            "s3FilesConfiguration": {
                "accessPointArn": "arn:aws:s3files:us-west-2:<account-id>:file-system/<fs-id>/access-point/<ap-id>",
                "fileSystemArn": "arn:aws:s3files:us-west-2:<account-id>:file-system/<fs-id>",
                "mountPath": "/mnt/s3data"
            }
        }
    ]
)
```

### セッション開始時にマウント

```python
# データプレーン: セッション単位でマウント設定
dp = boto3.client("bedrock-agentcore", region_name="us-west-2")

response = dp.start_code_interpreter_session(
    codeInterpreterIdentifier="<code-interpreter-id>",
    name="data-analysis-session",
    sessionTimeoutSeconds=3600,
    filesystemConfigurations=[
        {
            "s3FilesConfiguration": {
                "accessPointArn": "arn:aws:s3files:us-west-2:<account-id>:file-system/<fs-id>/access-point/<ap-id>",
                "fileSystemArn": "arn:aws:s3files:us-west-2:<account-id>:file-system/<fs-id>",
                "mountPath": "/mnt/s3data"
            }
        }
    ]
)

session_id = response["sessionId"]
# セッション内で /mnt/s3data にアクセス可能
```

### EFS マウントの設定

```python
response = cp.create_code_interpreter(
    name="shared-tools-code-interpreter",
    executionRoleArn="arn:aws:iam::<account-id>:role/CodeInterpreterExecutionRole",
    networkConfiguration={
        "networkMode": "VPC",
        "vpcConfig": {
            "subnets": ["subnet-xxx", "subnet-yyy"],
            "securityGroups": ["sg-xxx"]
        }
    },
    filesystemConfigurations=[
        {
            "efsConfiguration": {
                "accessPointArn": "arn:aws:elasticfilesystem:us-west-2:<account-id>:access-point/<ap-id>",
                "fileSystemArn": "arn:aws:elasticfilesystem:us-west-2:<account-id>:file-system/<fs-id>",
                "mountPath": "/mnt/efs"
            }
        }
    ]
)
```

### S3 Files + EFS を同時マウント

```python
filesystemConfigurations=[
    {
        "s3FilesConfiguration": {
            "accessPointArn": "arn:aws:s3files:us-west-2:<account-id>:file-system/<fs-id>/access-point/<ap-id>",
            "fileSystemArn": "arn:aws:s3files:us-west-2:<account-id>:file-system/<fs-id>",
            "mountPath": "/mnt/s3data"
        }
    },
    {
        "efsConfiguration": {
            "accessPointArn": "arn:aws:elasticfilesystem:us-west-2:<account-id>:access-point/<ap-id>",
            "fileSystemArn": "arn:aws:elasticfilesystem:us-west-2:<account-id>:file-system/<fs-id>",
            "mountPath": "/mnt/efs"
        }
    }
]
```

### ファイルシステムマウントの前提条件

1. **VPC モード必須** — ファイルシステムマウントには VPC ネットワークモードが必要
2. **IAM権限** — 実行ロールに以下を付与：

S3 Files の場合:
```json
{
  "Effect": "Allow",
  "Action": [
    "s3files:ClientMount",
    "s3files:ClientWrite",
    "s3files:GetAccessPoint"
  ],
  "Resource": "arn:aws:s3files:<region>:<account-id>:file-system/<file-system-id>",
  "Condition": {
    "ArnEquals": {
      "s3files:AccessPointArn": "arn:aws:s3files:<region>:<account-id>:file-system/<fs-id>/access-point/<ap-id>"
    }
  }
}
```

EFS の場合:
```json
{
  "Effect": "Allow",
  "Action": [
    "elasticfilesystem:ClientMount",
    "elasticfilesystem:ClientWrite"
  ],
  "Resource": "arn:aws:elasticfilesystem:<region>:<account-id>:file-system/<file-system-id>",
  "Condition": {
    "ArnEquals": {
      "elasticfilesystem:AccessPointArn": "arn:aws:elasticfilesystem:<region>:<account-id>:access-point/<ap-id>"
    }
  }
}
```

3. **セキュリティグループ** — Code Interpreter SG からマウントターゲット SG へ TCP 2049 (NFS) をアウトバウンド許可

---

## 必要なIAM権限

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CodeInterpreterAccess",
      "Effect": "Allow",
      "Action": [
        "bedrock-agentcore:CreateCodeInterpreter",
        "bedrock-agentcore:GetCodeInterpreter",
        "bedrock-agentcore:ListCodeInterpreters",
        "bedrock-agentcore:DeleteCodeInterpreter",
        "bedrock-agentcore:StartCodeInterpreterSession",
        "bedrock-agentcore:StopCodeInterpreterSession",
        "bedrock-agentcore:GetCodeInterpreterSession",
        "bedrock-agentcore:ListCodeInterpreterSessions",
        "bedrock-agentcore:InvokeCodeInterpreter"
      ],
      "Resource": "arn:aws:bedrock-agentcore:<Region>:<ACCOUNT_ID>:code-interpreter/*"
    }
  ]
}
```

---

## 依存パッケージのインストール

```bash
# Python SDK
pip install bedrock-agentcore boto3

# Strands Agents 統合
pip install bedrock-agentcore strands-agents strands-agents-tools

# LangChain 統合
pip install bedrock-agentcore langchain langchain_aws

# TypeScript SDK
npm install bedrock-agentcore @strands-agents/sdk
```

---

## ユースケース

| ユースケース | 説明 |
|---|---|
| データ分析 | CSV/Excel/JSONの読み込み、統計分析、可視化 |
| 数値計算 | 数学的計算、最適化問題、シミュレーション |
| コード検証 | エージェントが生成したコードの実行・テスト |
| レポート生成 | データからグラフやPDFレポートを自動生成 |
| ETL処理 | S3上の大規模データの変換・集約 |
| 機械学習 | モデルのトレーニング・推論・評価 |
| VPC内データ処理 | プライベートDBへのクエリ、内部APIアクセス |

---

## ベストプラクティス

- `code_session` コンテキストマネージャを使ってセッションの確実なクリーンアップを保証
- コードスニペットは短く、特定タスクに集中させる
- `clearContext: False` で複数ステップの処理を行う（変数を保持）
- 大規模データは S3 Files マウントを使い、APIサイズ制限を回避
- try/except でエラーハンドリングを含める
- セッション終了時にリソースを必ず解放

---

## 参考リンク

- [公式ドキュメント: Code Interpreter](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/code-interpreter-tool.html)
- [直接実行ガイド](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/code-interpreter-using-directly.html)
- [Strands連携](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/code-interpreter-using-strands.html)
- [VPC設定](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-vpc.html)
- [ファイルシステム設定](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/code-interpreter-filesystem-configurations.html)
- [プリインストールライブラリ一覧](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/code-interpreter-preinstalled-libraries.html)
- [AWSブログ: Introducing AgentCore Code Interpreter](https://aws.amazon.com/blogs/machine-learning/introducing-the-amazon-bedrock-agentcore-code-interpreter/)
