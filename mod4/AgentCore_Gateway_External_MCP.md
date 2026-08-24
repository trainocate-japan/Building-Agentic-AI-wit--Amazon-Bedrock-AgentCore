# AgentCore Gateway から外部MCPサーバーを定義する

## 概要

AgentCore Gateway は、外部のMCPサーバーをターゲットとして登録し、エージェントから統一的にアクセスできるようにします。認証方式として **IAM (SigV4)**、**OAuth2**、**API Key** の3種類をサポートしています。

## 認証方式一覧

| 方式 | ユースケース |
|---|---|
| **IAM (SigV4)** | AgentCore Runtime上のMCP、API Gateway背後のMCP、Lambda Function URL |
| **OAuth2** | GitHub、Slack等の外部SaaSが提供するMCPサーバー |
| **API Key** | 独自のAPIキー認証を使うMCPサーバー |

---

## 1. IAM (SigV4) 認証 — AWS MCPサーバー向け

AgentCore Runtime上にデプロイしたMCPサーバーや、API Gateway背後のMCPサーバーなど。

### `service` の値（ホスト先による）

| 値 | ホスト先 |
|---|---|
| `bedrock-agentcore` | AgentCore Runtime上のMCPサーバー、別のGateway |
| `execute-api` | Amazon API Gateway背後 |
| `lambda` | Lambda Function URL |

### Boto3 の例

```python
import boto3

agentcore_client = boto3.client('bedrock-agentcore-control')

target = agentcore_client.create_gateway_target(
    gatewayIdentifier="your-gateway-id",
    name="AwsMCPTarget",
    targetConfiguration={
        "mcp": {
            "mcpServer": {
                "endpoint": "https://my-server.bedrock-agentcore.us-west-2.api.aws"
            }
        }
    },
    credentialProviderConfigurations=[
        {
            "credentialProviderType": "GATEWAY_IAM_ROLE",
            "credentialProvider": {
                "iamCredentialProvider": {
                    "service": "bedrock-agentcore",
                    "region": "us-west-2"
                }
            }
        }
    ]
)
```

### AWS CLI の例

```bash
aws bedrock-agentcore-control create-gateway-target \
    --gateway-identifier "your-gateway-id" \
    --name "MyMCPTarget" \
    --target-configuration '{
        "mcp": {
            "mcpServer": {
                "endpoint": "https://my-server.bedrock-agentcore.us-west-2.api.aws"
            }
        }
    }' \
    --credential-provider-configurations '[{
        "credentialProviderType": "GATEWAY_IAM_ROLE",
        "credentialProvider": {
            "iamCredentialProvider": {
                "service": "bedrock-agentcore",
                "region": "us-west-2"
            }
        }
    }]'
```

---

## 2. OAuth2 認証 — GitHub等の外部SaaS MCPサーバー

### Boto3 の例

```python
target = agentcore_client.create_gateway_target(
    gatewayIdentifier="your-gateway-id",
    name="GitHubMCPTarget",
    targetConfiguration={
        "mcp": {
            "mcpServer": {
                "endpoint": "https://my-mcp-server.example.com"
            }
        }
    },
    credentialProviderConfigurations=[
        {
            "credentialProviderType": "OAUTH",
            "credentialProvider": {
                "oauthCredentialProvider": {
                    "providerArn": "arn:aws:bedrock-agentcore:us-west-2:123456789012:token-vault/default/oauth2credentialprovider/my-oauth-provider",
                    "scopes": ["read:user"]
                }
            }
        }
    ]
)
```

### CDK の例（GitHub OAuth）

```python
from aws_cdk import aws_bedrockagentcore as agentcore
import aws_cdk as cdk

gateway = agentcore.Gateway(self, "MyGateway", gateway_name="my-gateway")

oauth = agentcore.OAuth2CredentialProvider.using_github(self, "GhOAuth",
    o_auth2_credential_provider_name="github-oauth",
    client_id="your-client-id",
    client_secret=cdk.SecretValue.unsafe_plain_text("your-client-secret")
)

gateway.add_mcp_server_target("Mcp",
    gateway_target_name="mcp-server",
    description="MCP with GitHub OAuth",
    endpoint="https://my-mcp-server.example.com",
    credential_provider_configurations=[
        agentcore.GatewayCredentialProvider.from_oauth_identity(oauth,
            scopes=["read:user"]
        )
    ]
)
```

### AWS CLI の例

```bash
aws bedrock-agentcore-control create-gateway-target \
    --gateway-identifier "your-gateway-id" \
    --name "MyMCPTarget" \
    --target-configuration '{
        "mcp": {
            "mcpServer": {
                "endpoint": "https://my-mcp-server.example.com"
            }
        }
    }' \
    --credential-provider-configurations '[{
        "credentialProviderType": "OAUTH",
        "credentialProvider": {
            "oauthCredentialProvider": {
                "providerArn": "arn:aws:bedrock-agentcore:us-west-2:123456789012:token-vault/default/oauth2credentialprovider/my-oauth-provider",
                "scopes": []
            }
        }
    }]'
```

---

## 3. API Key 認証 — 独自MCPサーバー

### Boto3 の例

```python
target = agentcore_client.create_gateway_target(
    gatewayIdentifier="your-gateway-id",
    name="CustomMCPTarget",
    targetConfiguration={
        "mcp": {
            "mcpServer": {
                "endpoint": "https://my-mcp-server.example.com"
            }
        }
    },
    credentialProviderConfigurations=[
        {
            "credentialProviderType": "API_KEY",
            "credentialProvider": {
                "apiKeyCredentialProvider": {
                    "providerArn": "arn:aws:bedrock-agentcore:us-west-2:123456789012:token-vault/default/apikeycredentialprovider/my-api-key",
                    "credentialLocation": "HEADER",
                    "credentialParameterName": "x-api-key",
                    "credentialPrefix": ""
                }
            }
        }
    ]
)
```

### AWS CLI の例

```bash
aws bedrock-agentcore-control create-gateway-target \
    --gateway-identifier "your-gateway-id" \
    --name "MyMCPTarget" \
    --target-configuration '{
        "mcp": {
            "mcpServer": {
                "endpoint": "https://my-mcp-server.example.com"
            }
        }
    }' \
    --credential-provider-configurations '[{
        "credentialProviderType": "API_KEY",
        "credentialProvider": {
            "apiKeyCredentialProvider": {
                "providerArn": "arn:aws:bedrock-agentcore:us-west-2:123456789012:token-vault/default/apikeycredentialprovider/my-api-key",
                "credentialLocation": "HEADER",
                "credentialParameterName": "x-api-key",
                "credentialPrefix": ""
            }
        }
    }]'
```

---

## ツール同期の仕組み

Gateway がMCPサーバーに接続すると、MCPプロトコルの `tools/list` を呼んでツール定義を自動取得・インデックスします。

ツールが更新された場合は `SynchronizeGatewayTargets` API で再同期:

```python
agentcore_client.synchronize_gateway_targets(
    gatewayIdentifier="your-gateway-id"
)
```

### 同期フロー

1. `SynchronizeGatewayTargets` API を呼び出し
2. Gateway が OAuth トークンを取得（OAuth認証の場合）
3. MCPサーバーに `initialize` セッションを確立
4. `tools/list` をページネーション付きで呼び出し（100ツールずつ）
5. ツール名にターゲット固有のプレフィックスを付けてインデックス化

---

## その他のターゲットタイプ

Gateway は MCPサーバー以外にも以下をターゲットとしてサポート：

| ターゲットタイプ | 説明 |
|---|---|
| Lambda 関数 | ツールスキーマ付きの Lambda を直接呼び出し |
| API Gateway REST API | 既存の REST API をツールとして公開 |
| OpenAPI スキーマ | OpenAPI 仕様からツールを自動生成 |
| Smithy モデル | Smithy 定義からツールを自動生成 |
| HTTP Runtime | AgentCore Runtime 上のエージェントに直接転送 |
| Connector (Knowledge Bases) | Bedrock Knowledge Bases を検索ツールとして公開 |
| Connector (Web Search) | マネージドWeb検索ツール |

---

## 参考リンク

- [Gateway ターゲット設定ドキュメント](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-add-target-api-target-config.html)
- [Gateway VPC Egress 設定](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-vpc-egress.html)
- [AWSブログ: Transform your MCP architecture with AgentCore Gateway](https://aws.amazon.com/blogs/machine-learning/transform-your-mcp-architecture-unite-mcp-servers-through-agentcore-gateway/)
