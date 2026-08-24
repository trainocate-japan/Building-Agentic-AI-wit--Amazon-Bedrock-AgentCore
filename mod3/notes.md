# Module 3 メモ — 認可パターンと AgentCore Identity

## SigV4 による AgentCore 呼び出し

- `route.ts` は Next.js API Route（サーバーサイド）で動作
- `BedrockAgentCoreClient` を生成するだけで、SDK v3 が自動的に SigV4 署名を付与
- Amplify Hosting にデプロイした場合、サービスロールの一時認証情報が環境変数として注入される
- コード上で認証情報をハードコードする必要はない
- 詳細コード: `invoke_agentcore_sigv4.ts`

## 認可パターンの比較（SigV4 / 2LO / 3LO）

### SigV4

- AWS ネイティブの署名方式
- IAM 認証情報（アクセスキー + シークレットキー + セッショントークン）で署名
- サーバー間通信や Amplify ホスティング環境で使用

### OAuth 2-Legged (2LO)

- 登場人物: クライアント（アプリ）⇔ 認可サーバー の2者間
- ユーザー介在なし
- Client Credentials Grant を使用
- ユースケース: サーバー間通信、バッチ処理

### OAuth 3-Legged (3LO)

- 登場人物: エンドユーザー ⇔ クライアント（アプリ）⇔ 認可サーバー の3者間
- ユーザーのログイン・同意が必要
- Authorization Code Grant (+ PKCE) を使用
- ユースケース: エンドユーザーが直接操作するモバイル/Web アプリ

| | 2LO | 3LO |
|---|---|---|
| ユーザーのログイン | 不要 | 必要 |
| トークン取得者 | アプリ自身 | ユーザーの代理としてアプリ |
| Grant Type | Client Credentials | Authorization Code |
| actor の識別 | アプリ単位 | ユーザー単位 |

## ワークロード ID (Workload Identity)

### 役割

- エージェントに「安定したアイデンティティ（身分証明）」を与えるエンティティ
- 主な役割は **AgentCore Identity サービスとの紐付け**
- ワークロード ID を起点に、トークン管理・OAuth フロー・認可が動作する

### 具体的な機能

- 一意の ARN でエージェントを識別
- Workload Access Token の発行基盤
- Token Vault（外部サービスのトークン保管）との連携
- OAuth2 フロー（2LO/3LO）の主体
- 「ユーザーAの代わりにエージェントXが操作」というスコープ付きトークン発行

### 手動作成方法

```bash
# AWS CLI
aws bedrock-agentcore-control create-workload-identity \
  --name "my-agent-identity" \
  --allowed-resource-oauth2-return-urls '["https://app.example.com/oauth/callback"]' \
  --tags '{"env": "prod"}'
```

```python
# boto3
client = boto3.client('bedrock-agentcore-control')
response = client.create_workload_identity(
    name='my-agent-identity',
    allowedResourceOauth2ReturnUrls=['https://app.example.com/oauth/callback']
)
```

### 補足

- Runtime や Gateway を作成すると自動的にワークロード ID も作られる
- 手動作成はカスタム名を付けたい場合や自己ホスト型ワークロードで必要
- アカウントに1つの Agent Identity Directory（`workload-identity-directory/default`）が自動生成される
