# Bedrock AgentCore Memory メモ

## create_memory と create_event の違い

| | `create_memory` | `create_event` |
|---|---|---|
| **役割** | メモリストア（箱）を作成する | メモリストアに会話イベント（中身）を記録する |
| **例え** | ノートを1冊用意する | ノートにページを書き込む |
| **呼び出し頻度** | 最初に1回 | 会話のたびに何度も |
| **主なパラメータ** | `name`, `description`, `event_expiry_days` | `memory_id`, `actor_id`, `session_id`, `messages` |

### create_memory — メモリリソースの定義

```python
from bedrock_agentcore.memory import MemoryClient

client = MemoryClient(region_name="us-east-1")

memory_id = client.create_memory(
    name="test_memory",
    description="Short-term memory only",
    event_expiry_days=7,   # 7日で自動削除
)
```

- 短期メモリの「入れ物」を作る
- 有効期限やメモリの種類（短期のみ/長期も含む）を設定する
- 返される `memory_id` を以降の操作で使う

### create_event — 会話のやり取りを保存

```python
memory_client.create_event(
    memory_id="mem-123",
    actor_id="user-123",
    session_id="sess_id",
    messages=[
        ("注文 #12345 の内容に問題があります", "USER"),
        ("申し訳ありません。注文を調べさせてください。", "ASSISTANT"),
        ("lookup_order(order_id='12345')", "TOOL"),
    ]
)
```

- 既存のメモリストアに対して、実際の会話メッセージを記録する
- `actor_id` と `session_id` で「誰の」「どのセッションの」会話かを紐づける
- 記録されたイベントは `get_event` や `list_events` で取り出せる

**まとめ**: `create_memory` は器を用意する操作、`create_event` はその器に会話データを入れる操作。1つのメモリに対して複数のイベントが蓄積されていく。

---

## 長期メモリの可視範囲（namespace）

長期メモリを他のユーザーに見せるかどうかは **namespace（名前空間）のパス設計** で制御する。

### 仕組み

`retrieve_memories` 時に指定する `namespace` が、どのメモリにアクセスできるかを決める。

```python
# ユーザー固有のメモリだけ取得
memories = memory_client.retrieve_memories(
    memory_id="mem-123",
    namespace="user/user-123",   # このユーザー専用
    query="注文に関する好み"
)

# 全ユーザー共通のメモリを取得
memories = memory_client.retrieve_memories(
    memory_id="mem-123",
    namespace="shared",          # 共有空間
    query="システム全般のナレッジ"
)
```

### パスの設計例

| namespace パス | 見える範囲 |
|---|---|
| `user/{actor_id}` | 特定ユーザーだけに見える個人メモリ |
| `team/{team_id}` | チーム内で共有されるメモリ |
| `shared` / `global` | 全ユーザーに見えるメモリ |

### ポイント

- **書き込み時**に `namespace` を指定して、メモリをどのスコープに保存するか決める
- **読み取り時**に同じ `namespace` を指定することで、そのスコープのメモリだけが返される
- 「他のユーザーに見せるかどうか」は、イベント記録時に設定する namespace のパス設計次第

個人の好みや設定は `user/{id}` に、共通ナレッジは `shared` に保存する設計パターンが一般的。

---

## 長期メモリ戦略

| 戦略 | 説明 |
|---|---|
| サマリー | インタラクションの内容と結果の要約を作成 |
| ユーザー設定 | ユーザーの行動、インタラクションスタイル、選択肢の繰り返しパターンを保存して学習 |
| セマンティック | 事実、ドメイン固有の情報、技術的概念、およびそれらの関係性に関する知識を維持 |
| エピソード | ユーザーとシステムのインタラクションの意味のある断片をキャプチャし、時間の経過とともにコンテキストがどのように変化したかを理解 |
| カスタム | プロンプトをオーバーライドしてLLMを選択し、特定のドメインまたはユースケースに合わせてメモリの抽出と統合をカスタマイズ |
