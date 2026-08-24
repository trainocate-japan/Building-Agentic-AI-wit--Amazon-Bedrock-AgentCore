# Phase 3: Identity の設定 — アウトバウンド認証（Module 03 対応）

## 概要

AgentCore Identity でアウトバウンド認証を設定し、
外部 API（OpenWeatherMap）の API Key を安全に管理します。

---

## 前提: OpenWeatherMap API Key の取得

1. https://openweathermap.org/api にアクセス
2. 無料アカウントを作成（Sign Up）
3. アカウント作成後、API keys ページで Key を取得
4. 無料枠: 1,000 リクエスト/日（デモには十分）

> API Key が有効になるまで最大2時間かかる場合があります。事前に作成しておいてください。

---

## Step 1: アイデンティティ画面を開く

1. AWS マネジメントコンソール → **Bedrock** → **AgentCore**
2. 左ナビゲーションから **「アイデンティティ」** を選択

画面には以下が表示されます:
- 仕組みの図（Caller → Inbound Auth → Hosted Agent → Outbound Auth → External resources）
- **インバウンド認証**: 発信者がエージェントにアクセスすることを認証
- **アウトバウンド認証**: ランタイムまたはゲートウェイが外部リソースにアクセスする認証

---

## Step 2: アウトバウンド認証に API キーを追加

### 2-1. API キーの追加

1. 画面下部の **「アウトバウンド認証」** セクションを確認
2. **「アウトバウンド認証を追加」** ボタンをクリック
3. ドロップダウンから **「API キーを追加」** を選択

### 2-2. API キーの設定

ダイアログが表示されます:

| 項目 | 値 |
|:--|:--|
| 名前 | `openweathermap-api-key` |
| API キータイプ | **API キーのみ** を選択 |
| API キー値 | (OpenWeatherMap で取得した API Key を入力) |

> 名前に使える文字: a-z, A-Z, 0-9, _ (アンダースコア), - (ハイフン)。最大50文字。

3. **「追加」** をクリック

### 2-3. 作成確認

アウトバウンド認証の一覧に追加されます:

| 名前 | ARN | タイプ | プロバイダー |
|:--|:--|:--|:--|
| openweathermap-api-key | arn:aws:bedrock-agentcore:... | API Key | - |

この ARN を控えておきます（Gateway ターゲットの Outbound Auth で使用）。

---

## Step 3: Lambda 環境変数での API Key 設定（暫定）

> Phase 4 (Gateway) で Gateway のアウトバウンド認証として統合するまでの暫定対応として、
> Lambda 環境変数に直接 API Key を設定しておきます。

1. Lambda コンソール → `agentcore-weather-tool`
2. **「設定」** → **「環境変数」** → **「編集」**
3. 環境変数を追加:

| キー | 値 |
|:--|:--|
| OPENWEATHERMAP_API_KEY | (取得した API Key) |

4. **「保存」** をクリック

---

## Step 4: 天気 Lambda を実 API 版に更新

1. Lambda コンソール → `agentcore-weather-tool` → **「コード」** タブ
2. `lambda_function.py` を `demo/lambda/weather_tool/lambda_function.py` の内容で置き換え
3. **「Deploy」** をクリック

### テスト確認

テストイベント:
```json
{
    "name": "get_weather",
    "input": { "location": "東京" }
}
```

期待する結果:
```
🌤️ 東京 の天気情報（リアルタイム）:
  気温: 33.2℃
  天候: 晴れ（晴天）
  湿度: 62%
  風: 南 3.1m/s
```

---

## 講義ポイント

### インバウンド vs アウトバウンド

| 方向 | 質問 | 例 |
|:--|:--|:--|
| インバウンド | 「誰がエージェントを呼んでいるか？」 | Cognito JWT, IAM SigV4 |
| アウトバウンド | 「エージェントが何にアクセスしているか？」 | API Key, OAuth |

### API キータイプの選択

| タイプ | ユースケース |
|:--|:--|
| API キーのみ | シンプルな外部 API（OpenWeatherMap 等） |
| Secrets Manager を介した API キー | ローテーションが必要な本番環境 |

### なぜ Lambda 環境変数ではなく Identity で管理するか

| 観点 | Lambda 環境変数 | Identity (アウトバウンド認証) |
|:--|:--|:--|
| 管理場所 | 各 Lambda に分散 | AgentCore で一元管理 |
| 監査 | CloudTrail で追跡困難 | アクセスが Identity に紐づいて記録 |
| ローテーション | 各 Lambda を手動更新 | Identity 側で一括更新 |
| 共有 | Lambda 間でコピーが必要 | 複数のターゲットで同じ認証を共有可能 |

> 💡 「デモでは Lambda 環境変数に直書きしたが、本番では Identity のアウトバウンド認証で管理する。
> キーのローテーションや監査が一元化される」
