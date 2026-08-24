# フロントエンド: Cognito ログイン付き Web UI（インバウンド認証）

## 概要

Cognito User Pool で JWT を発行し、AgentCore Runtime に Bearer Token として
直接渡すインバウンド認証を実装します。API Gateway は不要です。

---

## アーキテクチャ

```
ユーザー (ブラウザ)
    │
    ├── Cognito User Pool にログイン
    │   └── JWT Access Token を取得
    ▼
React App (Amplify UI)
    │ Authorization: Bearer <JWT>
    │ HTTPS POST（直接）
    ▼
AgentCore Runtime (Inbound Auth: Cognito JWT)
    │ Runtime が Token を自動検証
    ▼
Secretary Agent (エージェント処理)
    │ MCP (SigV4)
    ▼
AgentCore Gateway → Lambda Tools
```

> API Gateway を挟まず、フロントエンドから AgentCore Runtime を直接呼び出す構成です。

---

## Step 1: Cognito User Pool の作成

### 1-1. Cognito コンソールを開く

1. AWS マネジメントコンソール → **Cognito**
2. **「ユーザープールを作成」** をクリック

### 1-2. アプリケーションの定義

| 項目 | 値 |
|:--|:--|
| アプリケーションタイプ | モバイルアプリ |
| アプリケーション名 | `secretary-agent-web` |

> 「モバイルアプリ」を選択するとクライアントシークレットなし（パブリッククライアント）で作成されます。

### 1-3. オプションの設定

| 項目 | 値 |
|:--|:--|
| サインイン識別子のオプション | E メール |
| サインアップに必要な属性 | email（デフォルト） |

### 1-4. リターン URL

`https://localhost:3000/` と入力（開発用。後でデプロイ先の URL に変更）。

### 1-5. 作成

**「ユーザーディレクトリを作成する」** をクリック。

### 1-6. 作成後に確認する値

1. **ユーザープール ID** — ユーザープール概要ページで確認（形式: `us-east-1_XXXXXXXXX`）
2. **アプリケーションクライアント ID** — 左メニュー「アプリケーションクライアント」→ `secretary-agent-web` をクリック

### 1-7. 認証フローの確認

1. アプリケーションクライアント `secretary-agent-web` を開く
2. **「認証フロー」** セクションに `ALLOW_USER_PASSWORD_AUTH` が含まれていることを確認
3. 含まれていなければ **「編集」** から追加して保存

---

## Step 2: Runtime に Inbound Auth を設定

AgentCore Runtime に Cognito JWT 検証を追加します。

### 2-1. AgentCore アイデンティティ画面を開く

1. AgentCore コンソール → **アイデンティティ**
2. **インバウンド認証** セクション

### 2-2. インバウンド認証の作成

Runtime に紐づくインバウンド認証を設定:

| 項目 | 値 |
|:--|:--|
| Discovery URL | `https://cognito-idp.us-east-1.amazonaws.com/<USER_POOL_ID>/.well-known/openid-configuration` |
| Allowed Clients | `<APP_CLIENT_ID>` |

> Discovery URL は Cognito User Pool の OIDC エンドポイントです。
> Runtime がこの URL から公開鍵を取得して JWT を検証します。

---

## Step 3: テストユーザーの作成

### 3-1. コンソールで作成

1. Cognito → ユーザープール → **「ユーザー」** タブ → **「ユーザーを作成」**
2. 設定:
   | 項目 | 値 |
   |:--|:--|
   | ユーザー名 | `demo-instructor` |
   | E メールアドレス | (自分のメールアドレス) |
   | 一時パスワード | (任意) |

---

## Step 4: フロントエンドの設定

### 4-1. 環境変数ファイルの作成

```bash
cd demo/frontend
cp .env.example .env
```

`.env` を編集:
```
VITE_USER_POOL_ID=us-east-1_XXXXXXXXX
VITE_USER_POOL_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
VITE_RUNTIME_ENDPOINT=https://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/<RUNTIME_ID>/invoke?qualifier=prod
```

### 4-2. 依存パッケージのインストール

```bash
npm install
```

### 4-3. ローカルで起動

```bash
npm run dev
```

→ http://localhost:3000 にアクセス

### 4-4. 動作確認

1. Cognito ログイン画面が表示される
2. テストユーザーでログイン（初回は一時パスワード変更あり）
3. チャット画面で「今日のスケジュールを教えて」と入力
4. 思考中インジケーター（ドットアニメーション）が表示される
5. ストリーミングで応答が表示される

---

## Step 5: Amplify Hosting へのデプロイ (オプション)

```bash
npm run build
```

Amplify コンソール → 「Deploy without Git provider」→ `dist/` をアップロード。

---

## 講義ポイントまとめ

| トピック | 説明 |
|:--|:--|
| インバウンド認証 | Cognito JWT で「誰がアクセスしているか」を Runtime が自動検証 |
| API Gateway 不要 | Runtime が直接 JWT 検証するため中間層が不要 |
| ストリーミング | text/event-stream で逐次応答を表示 |
| セキュリティ | Token 無効時は Runtime が 401 で拒否 |

### 認証フロー

```
1. ユーザーが Cognito にログイン → JWT Access Token 取得
2. フロントエンドが HTTPS POST + Authorization: Bearer <JWT>
3. Runtime が Discovery URL から公開鍵取得 → JWT 検証
4. 検証 OK → エージェント実行
5. 検証 NG → 401 Unauthorized
```

> 「AWS SDK を使わず直接 HTTPS で呼ぶ。これが OAuth 統合のポイント。
> Runtime が Cognito の公開鍵で JWT を検証するので、アプリ側のコードは
> Token をヘッダーに付けるだけでよい」
