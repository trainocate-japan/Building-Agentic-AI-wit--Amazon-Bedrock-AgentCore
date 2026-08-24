# Phase 5: AgentCore Memory の作成（Module 05 対応）

## 概要

AgentCore Memory を使って、エージェントにセッション間で持続する記憶を与えます。
短期メモリ（会話コンテキスト）と長期メモリ（ユーザープリファレンス）を設定します。

---

## Step 1: コンセプトの説明

> 💡 講義ポイント: 「エージェントはデフォルトでは毎回記憶喪失。
> 前回の会話で聞いた好みも次のセッションでは忘れている。
> Memory がこれを解決する」

### メモリの種類

| メモリタイプ | 用途 | 保持期間 |
|:--|:--|:--|
| 短期メモリ (Short-term) | セッション内の会話コンテキスト | イベント保持期間（設定可能） |
| 長期メモリ (Long-term) | セッションをまたぐ情報 | 永続 |

### 長期メモリ戦略

| 戦略 | 用途 | 例 |
|:--|:--|:--|
| USER_PREFERENCE | ユーザーの好み・設定 | 「お茶が好き」「午前に会議を入れない」 |
| SEMANTIC | 事実情報をベクトル化して保存 | 「プロジェクトXの期限は9月」 |
| EPISODIC | 体験・プロセスの記録 | 「前回のトラブルシュートで解決した方法」 |
| SUMMARY | 会話の要約 | 長い議論のサマリー |

---

## Step 2: マネジメントコンソールで Memory を作成

### 2-1. AgentCore Memory コンソールを開く

1. AWS マネジメントコンソール → **Bedrock** → **AgentCore**
2. 左ナビゲーションから **「Memory」** を選択

### 2-2. Memory の作成

1. **「Create memory」** をクリック

2. 基本設定:
   | 項目 | 値 |
   |:--|:--|
   | Memory name | `secretary-agent-memory` |
   | Short-term memory (raw event) expiration | `30 days` |

3. Additional configurations:
   | 項目 | 値 |
   |:--|:--|
   | Memory description | `秘書エージェントの会話メモリ。ユーザーの好みと過去の指示を記憶` |
   | KMS key | (デフォルト - AWS managed key) |

4. Long-term memory extraction strategies:

   **Strategy 1: USER_PREFERENCE**
   | 項目 | 値 |
   |:--|:--|
   | Strategy type | User Preference |
   | Name | `InstructorPreferences` |
   | Description | `講師の好みや設定を記憶する` |
   | Namespace | `secretary/instructor/{actorId}/preferences` |

   **Strategy 2: SEMANTIC**
   | 項目 | 値 |
   |:--|:--|
   | Strategy type | Semantic |
   | Name | `CourseInformation` |
   | Description | `研修や業務に関する事実情報を記憶する` |
   | Namespace | `secretary/instructor/{actorId}/facts` |

5. **「Create memory」** をクリック

### 2-3. 作成確認

```bash
aws bedrock-agentcore-control list-memories \
    --query "memories[].{Name:name, Id:memoryId, Status:status}" \
    --output table
```

---

## Step 3: Memory ID と戦略 ID を環境変数に設定

```bash
# Memory ID を取得
MEMORY_ID=$(aws bedrock-agentcore-control list-memories \
    --query "memories[?name=='secretary-agent-memory'].memoryId" \
    --output text)

export AGENTCORE_MEMORY_ID="${MEMORY_ID}"
echo "Memory ID: ${MEMORY_ID}"

# 戦略 ID を取得（コンソールの Memory 詳細画面 → Strategies タブで確認可能）
export MEMORY_PREFERENCE_STRATEGY_ID="<InstructorPreferences の Strategy ID>"
export MEMORY_SEMANTIC_STRATEGY_ID="<CourseInformation の Strategy ID>"
```

### Runtime デプロイ時の環境変数

| 環境変数 | 説明 |
|:--|:--|
| `AGENTCORE_MEMORY_ID` | AgentCore Memory の ID |
| `MEMORY_PREFERENCE_STRATEGY_ID` | USER_PREFERENCE 戦略の ID |
| `MEMORY_SEMANTIC_STRATEGY_ID` | SEMANTIC 戦略の ID |

> 💡 `agent_production.py` はこれらの環境変数が設定されている場合のみ Memory を有効化します。未設定の場合は Memory なしで動作します。

---

## Step 4: メモリ付きエージェントの実行

### 4-1. エージェント起動

```bash
cd demo/src
export AGENTCORE_MEMORY_ID="<上で取得した Memory ID>"
python -u agent_with_gateway.py
```

### 4-2. デモシナリオ

**Session 1: 好みを伝える**

```
👤 You: 私は緑茶が好きです。会議の時に用意しておいてください。
🤖 Secretary: 承知しました。記憶しました。会議の際は緑茶を用意するようにします。

👤 You: あと、午前中は集中タイムなので会議を入れないでください。
🤖 Secretary: 了解しました。午前中は会議を入れず、集中タイムとして確保します。記憶しました。
```

**Session 1 終了 → エージェント再起動**

```bash
# Ctrl+C で終了
# 再起動
python -u agent_with_gateway.py
```

**Session 2: 記憶の確認**

```
👤 You: 会議の準備で何か覚えていることはある？
🤖 Secretary: はい、以前お伝えいただいた内容を覚えています:
  - 会議の際は緑茶を用意する
  - 午前中は集中タイムのため会議を入れない

👤 You: 明日の9時に会議を入れて
🤖 Secretary: 申し訳ありませんが、午前中は集中タイムとのことでしたので、
  午後の時間帯をお勧めします。14時はいかがでしょうか？
```

> 💡 講義ポイント: 「セッションが切れてもユーザーの好みを覚えている。
> これが USER_PREFERENCE 戦略の効果」

---

## Step 5: メモリの中身を確認

### 5-1. コンソールで確認

1. Memory のページ → 作成した Memory をクリック
2. **「Events」** タブ → 保存されたイベントの一覧を確認
3. **「Extracted memories」** → 長期メモリに抽出された内容を確認

### 5-2. CLI で確認

```bash
# メモリの詳細を取得
aws bedrock-agentcore-control get-memory \
    --memory-id "${MEMORY_ID}" \
    --output json
```

---

## 講義ポイントまとめ

| トピック | 説明 |
|:--|:--|
| 短期 vs 長期 | 短期 = セッション内コンテキスト。長期 = セッション間の永続知識 |
| 戦略の組み合わせ | USER_PREFERENCE + SEMANTIC で好みと事実を分離管理 |
| Namespace 設計 | `secretary/instructor/{actorId}/preferences` と `secretary/instructor/{actorId}/facts` でユーザー・目的別に分離 |
| retrieval_config | `AgentCoreMemoryConfig` に `retrieval_config` を渡すことで、namespace ごとの長期メモリを自動取得 |
| 自動抽出 | 会話から自動的に重要情報を抽出・構造化 |
| エピソディック | 珍しい解決方法やプロセスを記憶 → 類似問題に適用 |

### agent_production.py での Memory 統合コード

```python
from bedrock_agentcore.memory.integrations.strands.config import (
    AgentCoreMemoryConfig,
    RetrievalConfig,
)
from bedrock_agentcore.memory.integrations.strands.session_manager import (
    AgentCoreMemorySessionManager,
)

# namespace ごとに RetrievalConfig を設定
retrieval_config = {}
retrieval_config[f"secretary/instructor/{actor_id}/preferences"] = RetrievalConfig()
retrieval_config[f"secretary/instructor/{actor_id}/facts"] = RetrievalConfig()

memory_config = AgentCoreMemoryConfig(
    memory_id=MEMORY_ID,
    session_id=session_id,
    actor_id=actor_id,
    retrieval_config=retrieval_config,
)
session_manager = AgentCoreMemorySessionManager(
    agentcore_memory_config=memory_config
)

# Agent に session_manager を渡す
agent = Agent(
    model=model,
    system_prompt=system_prompt,
    tools=tools,
    session_manager=session_manager,
)
```

> 💡 `retrieval_config` に namespace を指定すると、エージェント起動時に該当 namespace の長期メモリが自動的にコンテキストに注入されます。

### 長期メモリ vs RAG

| 観点 | Long-term Memory | RAG |
|:--|:--|:--|
| データソース | 会話から自動抽出 | 事前に用意したドキュメント |
| 更新頻度 | リアルタイム（対話ごと） | バッチ更新 |
| パーソナライズ | ユーザー固有の情報 | 共有知識 |
| 適用場面 | 好み・経験の記憶 | 社内ドキュメント検索 |

> 💡 「Memory は『エージェントの成長』を可能にする。使えば使うほど
> ユーザーを理解し、よりパーソナライズされた対応ができるようになる」
