# 同意ポータル（Consent Portal）検証手順 — Cognito を primary IdP に使う

AgentCore Identity の新機能「同意ポータル」を、検証専用リソースだけで動作確認するための手順です。
既存デモのリソース（Gateway / Cognito / Identity）には一切手を触れず、すべて新規に作成します。

---

## 0. これは何か / なぜ Cognito か

同意ポータル（Consent Portal）は、AWS がホストするマネージドなポータルです。
エンドユーザーを OIDC IdP でサインインさせ、エージェントがユーザーの代理で
下流リソースにアクセスする前に「同意（consent）」を集めます。OAuth フローはサーバー側で
完結し、ブラウザはトークンを保持しません。

- 1つの同意ポータルは、1つの AgentCore Gateway（source）に紐づく
- ポータルは OAuth2 credential provider を通じて、Gateway のインバウンド JWT authorizer が
  信頼するのと同じ OIDC issuer を参照する

### primary IdP に使える IdP の制約（重要）

同意ポータルの **primary IdP（ユーザーがサインインする先）** は、次を満たす必要があります。

- **JWT アクセストークンを発行する OIDC IdP であること**
- OIDC discovery ドキュメントを公開していること

このため、ID トークンを発行せず discovery を公開しない OAuth2 専用ベンダー
（GitHub, Slack, Salesforce, Atlassian, LinkedIn など）や、**Google** は
**primary IdP としては使えません**（これらはゲートウェイターゲット向けの
アウトバウンドプロバイダーとしては引き続き有効）。

→ 検証用の primary IdP には **Amazon Cognito** を使います。Cognito は JWT アクセストークンを
発行し、OIDC discovery を公開するため、要件を満たします。

出典（要約。ライセンス配慮のため内容は言い換えています）:
- [Configure a consent portal](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity-consent-portal.html)
- [Consent portal prerequisites](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity-consent-portal-prerequisites.html)
- [Consent portal execution role](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity-consent-portal-execution-role.html)
- [Create a consent portal with the console](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity-create-consent-portal-console.html)
- [Create a consent portal with the AWS CLI](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity-create-consent-portal.html)
- [Amazon Cognito（provider 設定）](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity-idp-cognito.html)

---

## 全体像

```
エンドユーザー
   │  ①サインイン（Cognito Hosted UI）
   ▼
[同意ポータル（AWS ホスト）] ──②同意── ▶ Gateway のターゲット（接続先）
   │
   └─ primary IdP = Cognito（JWT / OIDC）
      Gateway インバウンド認証 = JWT（同じ Cognito issuer を参照）
```

作成順序（依存関係の都合でこの順番が重要）:

1. Cognito ユーザープール + アプリクライアント（authorization code grant + client secret）+ ドメイン + テストユーザー
2. Cognito を参照する OAuth2 credential provider を Identity に作成 → `callbackUrl` を控える
3. その `callbackUrl` を Cognito アプリクライアントの Allowed callback URLs に登録
4. JWT インバウンド認証の Gateway を新規作成（Cognito の discovery URL を使用）
5. 同意ポータルの実行ロール（IAM）を作成
6. 同意ポータルを作成（コンソール推奨）→ `ACTIVE` 待ち → `portalUrl` 取得
7. `<portalUrl>/callback` を Cognito アプリクライアントの Allowed callback URLs に追加
8. `portalUrl` をブラウザで開き、テストユーザーでサインイン → 同意画面を確認

> 用途上、`callbackUrl`（手順2 由来）と `<portalUrl>/callback`（手順6 由来）の
> **2つの異なるコールバック URL** を Cognito のアプリクライアントに登録することになります。
> 前者は credential provider のセッションバインディング用、後者は同意ポータル本体のサインイン用です。

以下では検証しやすいよう、リージョンは `us-east-1` を前提にします（既存デモに合わせています）。
別リージョンの場合は各コマンド・URL のリージョンを読み替えてください。

---

## 事前準備

- 最新の AWS CLI と `jq` がインストール済み
- `aws configure` 済み（リージョン `us-east-1`）
- 権限: 検証目的なら `BedrockAgentCoreFullAccess` + Cognito/IAM 操作権限があれば十分
  （本番では最小権限に絞ること）

作業用の環境変数:

```bash
export REGION=us-east-1
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
```

---

## Step 1: Cognito ユーザープール（primary IdP）を新規作成

### 1-1. ユーザープールとアプリクライアント

```bash
# ユーザープール作成
export POOL_ID=$(aws cognito-idp create-user-pool \
  --pool-name "consent-portal-verify-pool" \
  --policies '{"PasswordPolicy":{"MinimumLength":8}}' \
  --region $REGION | jq -r '.UserPool.Id')
echo "POOL_ID=$POOL_ID"

# アプリクライアント作成（client secret あり / authorization code grant 有効）
# ※ callback URL は後の Step 3 / Step 7 で追加するため、ここでは仮値を入れておく
export CLIENT_JSON=$(aws cognito-idp create-user-pool-client \
  --user-pool-id $POOL_ID \
  --client-name "consent-portal-verify-client" \
  --generate-secret \
  --allowed-o-auth-flows code \
  --allowed-o-auth-scopes "openid" "email" "profile" \
  --allowed-o-auth-flows-user-pool-client \
  --supported-identity-providers "COGNITO" \
  --callback-urls '["https://example.com/placeholder"]' \
  --region $REGION)

export CLIENT_ID=$(echo $CLIENT_JSON | jq -r '.UserPoolClient.ClientId')
export CLIENT_SECRET=$(echo $CLIENT_JSON | jq -r '.UserPoolClient.ClientSecret')
echo "CLIENT_ID=$CLIENT_ID"
echo "CLIENT_SECRET=$CLIENT_SECRET"
```

> `--allowed-o-auth-flows code` = Authorization Code Grant（＝3LO の本体）。
> `openid` スコープは同意ポータルが常に要求するため必須です。

### 1-2. Hosted UI 用ドメイン

```bash
# ドメインプレフィックスは全世界で一意である必要がある。適宜変更する。
export DOMAIN_PREFIX="consent-verify-$(echo $ACCOUNT_ID | tail -c 7)"
aws cognito-idp create-user-pool-domain \
  --domain "$DOMAIN_PREFIX" \
  --user-pool-id $POOL_ID \
  --region $REGION
echo "Cognito domain: https://$DOMAIN_PREFIX.auth.$REGION.amazoncognito.com"
```

### 1-3. テストユーザー作成

```bash
aws cognito-idp admin-create-user \
  --user-pool-id $POOL_ID \
  --username "testuser" \
  --temporary-password "TempPass#123" \
  --message-action SUPPRESS \
  --region $REGION > /dev/null

aws cognito-idp admin-set-user-password \
  --user-pool-id $POOL_ID \
  --username "testuser" \
  --password "VerifyPass#123" \
  --permanent \
  --region $REGION > /dev/null

echo "test user: testuser / VerifyPass#123"
```

### 1-4. discovery URL を控える（Step 4 の Gateway で使用）

```bash
export DISCOVERY_URL="https://cognito-idp.$REGION.amazonaws.com/$POOL_ID/.well-known/openid-configuration"
echo "DISCOVERY_URL=$DISCOVERY_URL"
```

---

## Step 2: OAuth2 credential provider（Cognito）を作成

Cognito は「included（カスタム）OAuth2 provider」として、authorization / token / issuer の
各エンドポイントを明示して登録します。

```bash
export COGNITO_DOMAIN="https://$DOMAIN_PREFIX.auth.$REGION.amazoncognito.com"

export CP_RESPONSE=$(aws bedrock-agentcore-control create-oauth2-credential-provider \
  --region $REGION \
  --name "consent-portal-cognito-idp" \
  --credential-provider-vendor "CognitoOauth2" \
  --oauth2-provider-config-input "{
    \"includedOauth2ProviderConfig\": {
      \"clientId\": \"$CLIENT_ID\",
      \"clientSecret\": \"$CLIENT_SECRET\",
      \"authorizationEndpoint\": \"$COGNITO_DOMAIN/oauth2/authorize\",
      \"tokenEndpoint\": \"$COGNITO_DOMAIN/oauth2/token\",
      \"issuer\": \"https://cognito-idp.$REGION.amazonaws.com/$POOL_ID\"
    }
  }" \
  --output json)

export CP_ARN=$(echo $CP_RESPONSE | jq -r '.credentialProviderArn')
export CP_CALLBACK_URL=$(echo $CP_RESPONSE | jq -r '.callbackUrl')
echo "CP_ARN=$CP_ARN"
echo "CP_CALLBACK_URL=$CP_CALLBACK_URL"
```

`callbackUrl` は credential provider ごとに一意で、次のような形式です:

```
https://bedrock-agentcore.us-east-1.amazonaws.com/identities/oauth2/callback/XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
```

これはセッションバインディング（クロスプロバイダーのリプレイ / CSRF 対策）のための URL です。

---

## Step 3: credential provider の callbackUrl を Cognito に登録

Step 2 で得た `CP_CALLBACK_URL` を、Cognito アプリクライアントの Allowed callback URLs に追加します。
（Step 1-1 のプレースホルダを置き換えます。後の Step 7 でポータル用 URL をさらに追加します。）

```bash
aws cognito-idp update-user-pool-client \
  --user-pool-id $POOL_ID \
  --client-id $CLIENT_ID \
  --allowed-o-auth-flows code \
  --allowed-o-auth-scopes "openid" "email" "profile" \
  --allowed-o-auth-flows-user-pool-client \
  --supported-identity-providers "COGNITO" \
  --callback-urls "[\"$CP_CALLBACK_URL\"]" \
  --region $REGION
```

> 末尾スラッシュを付けないこと。URL は完全一致で登録します。

---

## Step 4: JWT インバウンド認証の Gateway を新規作成

同意ポータルは、インバウンド認証タイプが **JWT** の Gateway にのみ紐づけられます
（既存デモの Gateway は IAM 認証なので流用不可）。ここでは検証用に新しい Gateway を作ります。

コンソールでの作成:

1. AWS マネジメントコンソール → **Bedrock** → **AgentCore** → **Gateways**
2. **「Create gateway」**
3. 基本設定:
   | 項目 | 値 |
   |:--|:--|
   | Gateway name | `consent-portal-verify-gateway` |
   | Description | `同意ポータル検証用 Gateway（JWT インバウンド）` |
4. **Inbound Authorization**:
   | 項目 | 値 |
   |:--|:--|
   | Authorization type | **Use JSON Web Tokens (JWT)** |
   | Discovery URL | Step 1-4 の `DISCOVERY_URL` |
   | Allowed clients | Step 1-1 の `CLIENT_ID` |
5. **「Create gateway」**
6. 作成された **Gateway ID** を控える（同意ポータルの source に使用）。

```bash
export GATEWAY_ID=<作成した Gateway ID>
```

> AWS は同意ポータル作成時に「Gateway の JWT authorizer」と「idpConfig の credential provider」が
> **同じ OIDC issuer を参照している**ことを検証します。両方とも同じ Cognito ユーザープールを
> 指しているので整合します。
>
> ターゲット（接続先）は今はまだ無くても同意ポータル自体は作成できます。ターゲットが無い場合、
> ポータルの Connections ページは「同意対象なし」で空表示になります。同意画面に接続を出したい場合は、
> ポータルが ACTIVE になった後にターゲットを追加します（後述の「発展」を参照）。

---

## Step 5: 同意ポータルの実行ロール（IAM）を作成

同意ポータルは、Gateway と credential provider の構成読み取り、および OAuth クライアントシークレット
取得のために IAM ロールを assume します。

> コンソールで同意ポータルを作る場合、この実行ロールは「デフォルトロールを作成」で
> 自動生成させることもできます（Step 6 参照）。手動で作る場合のみ本 Step を実施してください。

### 5-1. 信頼ポリシー

`trust-policy.json`（初回はポータル ARN が未確定なので `Condition` を省略可。ポータル作成後に
best practice として `Condition` を付け戻す）:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ConsentPortalAssumeRolePolicy",
      "Effect": "Allow",
      "Principal": { "Service": "bedrock-agentcore.amazonaws.com" },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": { "aws:SourceAccount": "ACCOUNT_ID_PLACEHOLDER" }
      }
    }
  ]
}
```

### 5-2. 権限ポリシー

`permissions-policy.json`（`GATEWAY_ID_PLACEHOLDER` を Step 4 の Gateway ID に置換）:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock-agentcore:GetGateway",
        "bedrock-agentcore:GetGatewayTarget",
        "bedrock-agentcore:ListGatewayTargets"
      ],
      "Resource": "arn:aws:bedrock-agentcore:us-east-1:ACCOUNT_ID_PLACEHOLDER:gateway/GATEWAY_ID_PLACEHOLDER"
    },
    {
      "Effect": "Allow",
      "Action": [
        "bedrock-agentcore:GetOauth2CredentialProvider",
        "bedrock-agentcore:ListOauth2CredentialProviders"
      ],
      "Resource": [
        "arn:aws:bedrock-agentcore:us-east-1:ACCOUNT_ID_PLACEHOLDER:token-vault/default/oauth2credentialprovider/*",
        "arn:aws:bedrock-agentcore:us-east-1:ACCOUNT_ID_PLACEHOLDER:token-vault/default"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "bedrock-agentcore:CompleteResourceTokenAuth",
        "bedrock-agentcore:GetResourceOauth2Token",
        "bedrock-agentcore:GetWorkloadAccessTokenForJWT"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [ "secretsmanager:GetSecretValue" ],
      "Resource": [
        "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID_PLACEHOLDER:secret:bedrock-agentcore-identity!default/oauth2/*"
      ],
      "Condition": {
        "StringEquals": {
          "aws:ResourceTag/aws:secretsmanager:owningService": "bedrock-agentcore-identity"
        }
      }
    }
  ]
}
```

### 5-3. ロール作成 & ポリシーアタッチ

```bash
# プレースホルダを実値に置換（macOS の sed。GNU sed は -i の書式が異なる点に注意）
sed -i '' "s/ACCOUNT_ID_PLACEHOLDER/$ACCOUNT_ID/g" trust-policy.json
sed -i '' "s/ACCOUNT_ID_PLACEHOLDER/$ACCOUNT_ID/g; s/GATEWAY_ID_PLACEHOLDER/$GATEWAY_ID/g" permissions-policy.json

aws iam create-role \
  --role-name consent-portal-verify-exec-role \
  --assume-role-policy-document file://trust-policy.json

aws iam put-role-policy \
  --role-name consent-portal-verify-exec-role \
  --policy-name consent-portal-permissions \
  --policy-document file://permissions-policy.json

export EXEC_ROLE_ARN=$(aws iam get-role \
  --role-name consent-portal-verify-exec-role \
  --query 'Role.Arn' --output text)
echo "EXEC_ROLE_ARN=$EXEC_ROLE_ARN"
```

---

## Step 6: 同意ポータルを作成

### 方法 A: コンソール（推奨・手っ取り早い）

1. AgentCore コンソール → **Gateways** → Step 4 で作った `consent-portal-verify-gateway` を開く
2. Gateway 詳細ページで **「Create Consent Portal」**
3. **Consent portal details**:
   - Gateway: `consent-portal-verify-gateway`（選択済み）
   - 名前: 生成値のまま or 任意（例 `consent-portal-verify`）
   - 説明: 任意
4. **IdP credential configurations**:
   - IdP credential provider: **`consent-portal-cognito-idp`**（Step 2 で作成したもの）
     - ※ スクショで「OAuth2 認証情報プロバイダーはありません」だった箇所に、これが表示される
   - Scopes: `openid`（必要なら `email`, `profile` を追加）
   - Audiences: なし（Cognito では通常不要）
5. **Permissions（IAM アクセス許可）**:
   - 手軽に済ませるなら **「デフォルトロールを作成」**（Step 5 を省略できる）
   - 手動作成した実行ロールを使うなら「別のサービスロールを使用」→ `consent-portal-verify-exec-role`
6. **「Create Portal」**
7. ステータスが **`ACTIVE`** になるまで待つ。ACTIVE になると **Consent portal URL** が表示される。

### 方法 B: AWS CLI

```bash
aws bedrock-agentcore-control create-consent-portal \
  --region $REGION \
  --name "consent-portal-verify" \
  --execution-role-arn "$EXEC_ROLE_ARN" \
  --idp-config "{
    \"credentialProviderArn\": \"$CP_ARN\",
    \"scopes\": [\"openid\", \"email\", \"profile\"]
  }" \
  --sources "[{ \"identifier\": \"$GATEWAY_ID\", \"type\": \"agentcore-gateway\" }]"
```

`ACTIVE` になるまでポーリングして `portalUrl` を取得:

```bash
export PORTAL_ID=<レスポンスの consentPortalId>

aws bedrock-agentcore-control get-consent-portal \
  --region $REGION \
  --consent-portal-identifier "$PORTAL_ID" \
  --query '{status:status, portalUrl:portalUrl, reason:statusReason}'
```

- `status` が `ACTIVE` → `portalUrl` を控える
- `status` が `FAILED` → `statusReason` を確認して原因を切り分け

```bash
export PORTAL_URL=<取得した portalUrl>
```

> `openid` は必ず `scopes` に含めること。設定した全スコープ + `openid` が IdP 側で
> 定義・許可されていないと、認可時に `invalid_scope` エラーになります。

---

## Step 7: portalUrl の callback を Cognito に登録

同意ポータル本体のサインイン用コールバック `<portalUrl>/callback` を、Cognito アプリクライアントの
Allowed callback URLs に追加します。Step 3 の credential provider callback と**併せて 2 つ**登録します。

```bash
aws cognito-idp update-user-pool-client \
  --user-pool-id $POOL_ID \
  --client-id $CLIENT_ID \
  --allowed-o-auth-flows code \
  --allowed-o-auth-scopes "openid" "email" "profile" \
  --allowed-o-auth-flows-user-pool-client \
  --supported-identity-providers "COGNITO" \
  --callback-urls "[\"$CP_CALLBACK_URL\", \"$PORTAL_URL/callback\"]" \
  --region $REGION
```

> `<portalUrl>/callback` は末尾スラッシュなしで完全一致登録。
> 末尾スラッシュがあると IdP 側が「未登録の callback」として拒否し、サインインに失敗します。

---

## Step 8: 動作確認（3LO 同意フロー）

1. ブラウザで `PORTAL_URL` を開く
2. Cognito Hosted UI にリダイレクトされる → テストユーザー（`testuser` / `VerifyPass#123`）でサインイン
3. サインインに成功すると同意ポータルのページに遷移する
   - ここまで到達 = primary IdP・credential provider・ポータル callback の設定が正しいことの確認になる
4. Gateway にターゲットがある場合は Connections ページに接続先が並び、同意（consent）操作ができる
   - ターゲットが無い場合はページが空表示（これは正常。設定検証としては 3 まで到達すれば OK）

---

## 発展: 同意対象（ターゲット）を出す

同意画面に「接続先」を表示して実際に consent 操作まで見せたい場合は、ポータルが `ACTIVE` に
なった後で Gateway にアウトバウンド認証付きのターゲットを追加します。ターゲットの return URL は
ポータルの `portalUrl` に依存するため、ポータル作成後に追加するのが正しい順序です。
詳細は [Configure a consent portal target](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity-consent-portal-target.html) を参照。

---

## クリーンアップ

検証後に不要なら以下を削除します（依存の逆順）。

```bash
# 同意ポータル
aws bedrock-agentcore-control delete-consent-portal \
  --region $REGION --consent-portal-identifier "$PORTAL_ID"

# 実行ロール（手動作成した場合）
aws iam delete-role-policy --role-name consent-portal-verify-exec-role --policy-name consent-portal-permissions
aws iam delete-role --role-name consent-portal-verify-exec-role

# credential provider
aws bedrock-agentcore-control delete-oauth2-credential-provider \
  --region $REGION --name "consent-portal-cognito-idp"

# Gateway はコンソールから削除（ターゲットを付けた場合は先にターゲットを削除）

# Cognito
aws cognito-idp delete-user-pool-domain --domain "$DOMAIN_PREFIX" --user-pool-id $POOL_ID --region $REGION
aws cognito-idp delete-user-pool --user-pool-id $POOL_ID --region $REGION
```

---

## トラブルシュート早見表

| 症状 | 主な原因 | 対処 |
|:--|:--|:--|
| ポータルが `FAILED` | Gateway authorizer と credential provider の issuer 不一致 | 両方が同じ Cognito ユーザープールを指しているか確認（`get-consent-portal` の `statusReason`） |
| サインインで callback 拒否 | Allowed callback URLs 未登録 / 末尾スラッシュ | Step 3・Step 7 の URL を完全一致で登録し直す |
| `invalid_scope` | スコープが IdP 未定義 | アプリクライアントの許可スコープに `openid`（＋設定分）を含める |
| コンソールで credential provider が選べない | provider 未作成 or リージョン相違 | Step 2 を同一リージョンで実施 |
| provider 作成が Gateway より先で issuer 検証に迷う | 順序の誤解 | issuer は「ユーザープール」で決まるので、Gateway・provider どちらが先でも issuer は一致する |
