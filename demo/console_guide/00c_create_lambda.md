# 事前準備: Lambda 関数の作成

## 概要

AgentCore Gateway のターゲットとなる Lambda 関数を2つ作成します。
Phase 3 (Identity) と Phase 4 (Gateway) で使用します。

| Lambda 関数名 | 用途 | データソース |
|:--|:--|:--|
| `agentcore-schedule-tool` | スケジュール取得 | yamamanx.com/profile/ をスクレイピング |
| `agentcore-weather-tool` | 天気情報取得 | OpenWeatherMap API（API Key 必要） |

---

## Step 1: スケジュールツール Lambda の作成

### 1-1. Lambda コンソールを開く

1. AWS マネジメントコンソール → **Lambda**
2. **「関数の作成」** をクリック

### 1-2. 基本設定

| 項目 | 値 |
|:--|:--|
| 作成方法 | 一から作成 |
| 関数名 | `agentcore-schedule-tool` |
| ランタイム | Python 3.11 |
| アーキテクチャ | arm64 |
| 実行ロール | 基本的な Lambda アクセス権限で新しいロールを作成 |

**「関数の作成」** をクリック

### 1-3. コードの設定

1. コードソースエディタで `lambda_function.py` を開く
2. 内容をすべて削除し、`demo/lambda/schedule_tool/lambda_function.py` の内容を貼り付け
3. **「Deploy」** をクリック

### 1-4. タイムアウトの変更

Web スクレイピングのためデフォルト 3 秒では不足する場合があります。

1. **「設定」** タブ → **「一般設定」** → **「編集」**
2. タイムアウト: **15 秒** に変更
3. **「保存」** をクリック

### 1-5. テスト

1. **「テスト」** タブをクリック
2. テストイベント名: `TestGetSchedule`
3. イベント JSON:

```json
{
    "name": "get_schedule",
    "input": {}
}
```

4. **「テスト」** をクリック
5. 結果に「📅 スケジュール:」が含まれていれば成功

特定日付のテスト:
```json
{
    "name": "get_schedule",
    "input": { "date": "2026-08-05" }
}
```

---

## Step 2: 天気ツール Lambda の作成

### 2-1. 関数の作成

1. Lambda コンソール → **「関数の作成」**

| 項目 | 値 |
|:--|:--|
| 作成方法 | 一から作成 |
| 関数名 | `agentcore-weather-tool` |
| ランタイム | Python 3.11 |
| アーキテクチャ | arm64 |
| 実行ロール | 基本的な Lambda アクセス権限で新しいロールを作成 |

**「関数の作成」** をクリック

### 2-2. コードの設定

1. コードソースで `lambda_function.py` を開く
2. 内容を `demo/lambda/weather_tool/lambda_function.py` の内容で置き換え
3. **「Deploy」** をクリック

### 2-3. 環境変数の設定（API Key）

> OpenWeatherMap の API Key が必要です。
> 未取得の場合は https://openweathermap.org/api で無料アカウントを作成してください。

1. **「設定」** タブ → **「環境変数」** → **「編集」**
2. **「環境変数の追加」** をクリック:

| キー | 値 |
|:--|:--|
| OPENWEATHERMAP_API_KEY | (取得した API Key) |

3. **「保存」** をクリック

### 2-4. タイムアウトの変更

1. **「設定」** タブ → **「一般設定」** → **「編集」**
2. タイムアウト: **15 秒** に変更
3. **「保存」** をクリック

### 2-5. テスト

1. **「テスト」** タブ
2. テストイベント名: `TestGetWeather`
3. イベント JSON:

```json
{
    "name": "get_weather",
    "input": { "location": "東京" }
}
```

4. **「テスト」** をクリック
5. 結果に「🌤️ 東京 の天気情報（リアルタイム）」が含まれていれば成功

> API Key が無効または未アクティブの場合は「⚠️ API Key が無効です」と表示されます。
> 新規作成した Key は有効になるまで最大 2 時間かかることがあります。

---

## Step 3: Lambda ARN の確認

作成した2つの関数の ARN を控えておきます（Phase 4 の Gateway ターゲット追加で使用）。

各関数のページ上部に表示される ARN:
```
arn:aws:lambda:us-east-1:<ACCOUNT_ID>:function:agentcore-schedule-tool
arn:aws:lambda:us-east-1:<ACCOUNT_ID>:function:agentcore-weather-tool
```

---

## トラブルシューティング

| 症状 | 原因 | 対処 |
|:--|:--|:--|
| スケジュール取得で空が返る | yamamanx.com のページ構造変更 | ページを確認して パーサーを調整 |
| 天気取得で 401 エラー | API Key が無効 / 未アクティブ | Key 作成後 2 時間待つ、または Key を再確認 |
| タイムアウト | 外部アクセスに時間がかかっている | タイムアウトを 30 秒に延長 |
| import エラー | 追加ライブラリが必要 | このコードは標準ライブラリのみ使用、エラー内容を確認 |

---

## 次のステップ

- **Phase 3 (Identity):** 天気 Lambda の API Key を Identity で管理する
- **Phase 4 (Gateway):** 両方の Lambda を Gateway のターゲットとして登録する
