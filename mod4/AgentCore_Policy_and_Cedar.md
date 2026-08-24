# AgentCore Policy と Cedar（シーダー）

## AgentCore Policy とは

AgentCore Policy は、エージェントのツール呼び出しに対して**リアルタイムに許可/拒否を判定**する機能です。AgentCore Gateway と統合し、すべてのエージェントアクションをポリシーに基づいて制御します。

### 全体の流れ

```
ユーザー → エージェント → AgentCore Gateway
                              ↓
                     AgentCore Policy （動的なポリシーの評価）
                     ├── ポリシーライフサイクル管理（作成→テスト→適用→監視）
                     └── ポリシーオーサリング (NL2Cedar)（自然言語→Cedar変換）
                              ↓
                     許可 → ツール実行
                     拒否 → ブロック
                              ↓
                     AgentCore Observability（監査ログ）
```

---

## Cedar（シーダー）とは

**Cedar** は、AWSが開発した**認可ポリシー言語**です。読み方は「**シーダー**」（英語: /ˈsiːdər/）。元々は「杉の木」を意味する英単語です。

- **オープンソース**: https://github.com/cedar-policy
- **AWS Verified Permissions** と **AgentCore Policy** で使われている
- **デフォルト拒否**: 明示的に `permit` しない限り全て拒否
- **forbid が permit に勝つ**: 矛盾するポリシーがあれば安全側（拒否）に倒れる
- **副作用なし**: ファイルアクセスやネットワーク呼び出しがないので安全に評価できる
- **形式検証可能**: 数学的にポリシーの矛盾や冗長性を自動検出できる

### 基本構文

```cedar
permit(
    principal == User::"alice",       // 誰が
    action == Action::"view",          // 何を
    resource == Photo::"vacation.jpg"  // どこに
);
```

### AgentCore での使用例

```cedar
// 返金額1000ドル以下のみ許可
permit(
    principal is AgentCore::OAuthUser,
    action == AgentCore::Action::"ProcessRefund",
    resource == AgentCore::Gateway::"<gateway-arn>"
)
when {
    context.input.refundAmount <= 1000
};
```

### 条件付きポリシーの例

```cedar
// ゴールド会員のみが予約ツールを使える
permit(
    principal is AgentCore::OAuthUser,
    action == AgentCore::Action::"bookAppointment",
    resource
)
when {
    principal.hasTag("customer_tier") &&
    principal.getTag("customer_tier") == "Gold"
};
```

```cedar
// 特定のツールへのアクセスを明示的に禁止
forbid(
    principal,
    action == AgentCore::Action::"deleteAllRecords",
    resource
);
```

### なぜ Cedar を選んだのか

| 特性 | エージェントにとっての意味 |
|---|---|
| 決定論的 | LLMの曖昧さと無関係に、同じ入力なら必ず同じ結果 |
| 高速評価 | ループがないので ms 単位で判定可能 |
| 形式検証 | ポリシーの論理矛盾をデプロイ前に検出 |
| 人間可読 | ポリシー管理者が読んで理解できる |
| 安全 | 副作用なし、サンドボックス不要 |

---

## ポリシーライフサイクル管理

ポリシーの**作成 → テスト → 適用 → 更新 → 廃止**という一連の運用サイクルを管理する機能です。

| フェーズ | 内容 |
|---|---|
| **作成** | Cedar言語でポリシーを書く（またはNL2Cedarで生成） |
| **検証** | 自動的にスキーマに対してバリデーション（論理矛盾・冗長性の検出） |
| **テスト (LOG_ONLY)** | 本番トラフィックに対してポリシーを評価するが、実際には拒否しない |
| **適用 (ENFORCE)** | 確認後、ポリシーを有効化して実際に許可/拒否を実行 |
| **監視** | CloudWatch メトリクスとトレースで判定結果を監視 |
| **更新/廃止** | ポリシーのバージョン管理、不要ポリシーの削除 |

### 2つのモード

| 適用モード | 評価する？ | 実際に許可/拒否する？ | 用途 |
|---|---|---|---|
| **LOG_ONLY** | Yes | No（ログのみ） | 本番影響なしで事前検証 |
| **ENFORCE** | Yes | Yes | 本番適用 |

### LOG_ONLY モードの仕組み

```
リクエスト → Policy Engine
              ├─ ACTIVE ポリシー → 判定を実際に適用（許可/拒否）
              └─ LOG_ONLY ポリシー → 判定をログに記録するだけ（影響なし）
```

これにより「このポリシーを本番に入れたら何件ブロックされるか？」を安全に事前検証できます。LOG_ONLY で十分な期間観察した後、ACTIVE に昇格させるのが推奨ワークフローです。

---

## ポリシーオーサリング (NL2Cedar)

**自然言語からCedarポリシーを自動生成**する機能です。ポリシー管理者がCedar構文を知らなくても、日本語や英語でルールを記述すれば、AIがCedarコードに変換します。

### 3つのオーサリング方法

| 方法 | 説明 | 対象ユーザー |
|---|---|---|
| **自然言語 (NL2Cedar)** | 「返金額が10万円以下の場合のみ許可」→ Cedar に変換 | 非技術者 |
| **フォームベース** | UIのフォームで条件を選択して構築 | 管理者 |
| **直接記述** | Cedar 構文を直接書く | 開発者 |

### NL2Cedar の例

**入力（自然言語）:**
> 「OAuthユーザーが返金処理を行う場合、金額が1000ドル以下の場合のみ許可する」

**生成される Cedar:**
```cedar
permit(
    principal is AgentCore::OAuthUser,
    action == AgentCore::Action::"ProcessRefund",
    resource
)
when {
    context.input.refundAmount <= 1000
};
```

**入力:**
> 「ゴールド会員のみが予約ツールを使える」

**生成される Cedar:**
```cedar
permit(
    principal is AgentCore::OAuthUser,
    action == AgentCore::Action::"bookAppointment",
    resource
)
when {
    principal.hasTag("customer_tier") &&
    principal.getTag("customer_tier") == "Gold"
};
```

---

## 形式検証（Policy Analysis）

Cedar の数学的検証機能により、ポリシーの問題をデプロイ前に検出できます。

### 論理矛盾の検出

```cedar
// この policy は許可できるリクエストが存在しない（矛盾）
permit(
    principal is AgentCore::OAuthUser,
    action == AgentCore::Action::"ProcessRefund",
    resource
)
when {
    principal.getTag("customer_tier") == "Gold" &&
    principal.getTag("customer_tier") == "Platinum"  // ← 同時に成立しない
};
```
→ Cedarの形式検証が「この条件は常にfalseです」と警告

### 過剰な許可の検出

```cedar
// この policy は全リクエストを許可してしまう（過剰）
permit(
    principal is AgentCore::OAuthUser,
    action == AgentCore::Action::"ApplyBulkDiscount",
    resource
)
when {
    context.input.orderQuantity >= 100 ||
    context.input.orderQuantity < 100  // ← 全ての数値が該当
};
```
→ 「常にtrueになる条件です」と警告

---

## クイックスタート: AgentCore CLI でのセットアップ

```bash
# Gateway にポリシーエンジンを追加して作成
agentcore add gateway --name my-gateway
agentcore add policy-engine --gateway my-gateway
agentcore deploy

# ポリシーをテスト
agentcore test policy --gateway my-gateway
```

---

## Cedar の3つの構成要素

| 要素 | 説明 | 例 |
|---|---|---|
| **Principal** | 誰がリクエストしているか | `AgentCore::OAuthUser`, `User::"alice"` |
| **Action** | 何をしようとしているか | `AgentCore::Action::"ProcessRefund"` |
| **Resource** | どのリソースに対してか | `AgentCore::Gateway::"<gateway-arn>"` |

追加で `when` / `unless` 句で条件を付けられます：
- `when { ... }` — この条件を満たす場合のみ適用
- `unless { ... }` — この条件を満たす場合は適用しない

---

## 参考リンク

- [AgentCore Policy ドキュメント](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy-getting-started.html)
- [ポリシーのテスト (LOG_ONLY)](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy-test-a-policy.html)
- [AWSブログ: Secure AI agents with Policy in AgentCore](https://aws.amazon.com/blogs/machine-learning/secure-ai-agents-with-policy-in-amazon-bedrock-agentcore/)
- [AWSブログ: Why AgentCore chose Cedar](https://aws.amazon.com/blogs/security/why-policy-in-amazon-bedrock-agentcore-chose-cedar-for-securing-agentic-workflows/)
- [Cedar 公式サイト](https://www.cedarpolicy.com/)
- [Cedar GitHub](https://github.com/cedar-policy)
