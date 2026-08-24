# Smithy（スミシー）とは

## 概要

**Smithy** は、AWSが開発した**インターフェース定義言語（IDL）**とコード生成ツールセットです。APIの構造を一度定義すれば、そこから複数言語のクライアント・サーバー・ドキュメントを自動生成できます。

名前の由来は英語の「鍛冶屋（smithy）」。鍛冶屋が金属を打って道具を作るように、APIの「型」を打ち出すツール、というネーミングです。

## 主な特徴

- **プロトコル非依存**: REST、RPC、gRPC など特定のプロトコルに縛られない
- **AWSの全サービスがこれで定義されている**: AWS SDK（boto3、@aws-sdk 等）はすべて Smithy モデルから生成されている
- **10以上の言語に対応**: Java、Python、TypeScript、Go、Rust 等のクライアント/サーバーコードを生成
- **型安全**: 強い型付けで、入出力の正確なスキーマが保証される

## 構文の例

```smithy
namespace example.weather

service WeatherService {
    operations: [GetForecast]
}

operation GetForecast {
    input := {
        @required
        city: String
    }
    output := {
        temperature: Float
        description: String
    }
}
```

## AgentCore との関連

AgentCore Gateway でAPI定義をする際に、OpenAPI の代わりに Smithy モデルを使うこともできます。AWSサービスとの統合が深いので、特にAWSエコシステムでAPIを構築する場合に相性が良いです。

### Gateway に Smithy ターゲットを追加する例

```python
import boto3

agentcore_client = boto3.client('bedrock-agentcore-control')

target = agentcore_client.create_gateway_target(
    gatewayIdentifier="your-gateway-id",
    name="DynamoDBTarget",
    targetConfiguration={
        "mcp": {
            "smithyModel": {
                "s3": {
                    "uri": "s3://your-bucket/path/to/smithy-model.json",
                    "bucketOwnerAccountId": "123456789012"
                }
            }
        }
    },
    credentialProviderConfigurations=[
        {
            "credentialProviderType": "GATEWAY_IAM_ROLE"
        }
    ]
)
```

## OpenAPI との比較

| 項目 | Smithy | OpenAPI |
|---|---|---|
| 開発元 | AWS | OpenAPI Initiative |
| プロトコル | 非依存 | HTTP中心 |
| コード生成 | 標準機能 | サードパーティツール |
| AWS統合 | ネイティブ | 可能だが追加作業 |
| 記法 | 独自IDL | YAML/JSON |

## 参考リンク

- [Smithy公式サイト](https://smithy.io/)
- [Smithy 2.0 クイックスタート](https://smithy.io/2.0/quickstart.html)
- [AgentCore Gateway での Smithy 利用](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-building-smithy-targets.html)
