# ハンズオン: AgentCore Policy と NL2Cedar（マネジメントコンソール版）

> 所要時間の目安: **約 15〜20 分**
> 前提知識: [`AgentCore_Policy_and_Cedar.md`](./AgentCore_Policy_and_Cedar.md) を一読しておくとスムーズです。

## このハンズオンのゴール

デプロイ済みの **AgentCore Gateway** に **ポリシーエンジン** を紐付け、
自然言語で書いたルールを **NL2Cedar** で Cedar ポリシーに変換し、
まずは **LOG_ONLY モード** で安全に動作を観察するところまでを、
**AWS マネジメントコンソール**で操作しながら体験します。

「Cedar 構文を書かずに」「本番に影響を出さずに」ポリシーを試す、という
AgentCore Policy のいちばんおいしい部分だけを短時間でなぞる、デモ向けシナリオです。

```
自然言語ルール ──(NL2Cedar)──▶ Cedar ポリシー ──(LOG_ONLY)──▶ 判定結果をログで確認
   Step 3                        Step 3                        Step 4
```

---

## 前提条件

| 項目 | 要件 |
|:--|:--|
| AWS アカウント | AgentCore Policy が利用可能なリージョン |
| 既存リソース | デプロイ済みの AgentCore Gateway（`demo/` の Phase 4 で作成したものを流用可）|
| Gateway のツール | Lambda ターゲット（例: `get_weather` / `get_schedule`）が登録済み |
| IAM 権限 | AgentCore（Policy / Gateway）を操作できる権限 |

> 💡 まだ Gateway が無い場合は、`demo/console_guide/03_create_gateway.md` の手順で 1 つ作ってから戻ってきてください。
>
> ⚠️ **重要（Cedar の制約）**: Cedar はポリシー内でリソースのワイルドカードを許可しません。ポリシーには **Gateway の ARN** を必ず埋め込みます。そのため「Gateway は先に作成・デプロイ済み」であることが前提です。

---

## デモで使う登場人物（この Gateway の前提）

`demo/` の秘書エージェントを題材にします。Gateway に次の 2 つのツールが登録されている想定です。

| ツール | Gateway ターゲット名（例） | Cedar 上の action 名 |
|:--|:--|:--|
| 天気取得 | `WeatherTarget` | `AgentCore::Action::"WeatherTarget___get_weather"` |
| 予定取得 | `ScheduleTarget` | `AgentCore::Action::"ScheduleTarget___get_schedule"` |

> 📝 action 名は **`<ターゲット名>___<ツール名>`**（アンダースコア 3 つ区切り）という形式です。ご自身の Gateway の実際のターゲット名／ツール名に置き換えてください（コンソールの Gateway 詳細画面で確認できます）。

---

## Step 0: コンソールを開く（1 分）

1. AWS マネジメントコンソールにサインイン
2. 画面右上でリージョンが Gateway と同じであることを確認
3. **Amazon Bedrock AgentCore** のコンソールを開く
4. 左メニューから **Gateways** を開き、対象の Gateway を選択
5. Gateway 詳細画面で **Gateway ARN** をコピーしてメモ帳に控えておく（後で Cedar に貼り付けます）

### 講義ポイント
- Policy は Gateway の「境界」で効く機能なので、常に Gateway とセットで考える

---

## Step 1: ポリシーエンジンを作成する（3 分）

ポリシーエンジンは「その Gateway に対する許可/拒否ルールの入れ物」です。

1. AgentCore コンソールの左メニューから **Policy engines**（ポリシーエンジン）を開く
2. **Create policy engine**（ポリシーエンジンの作成）をクリック
3. 次を入力:
   - **Name**: `handson-policy-engine`
   - **Description**（任意）: `Hands-on for NL2Cedar`
4. **Create**（作成）をクリック
5. 作成後、詳細画面で **Policy engine ID / ARN** を控えておく

### 講義ポイント
- この時点ではポリシーが 1 件も無い = **デフォルト拒否**（deny-by-default）
- まだ Gateway には紐付けていない。紐付けは Step 4 で行う（先に中身を用意する流れ）

---

## Step 2: 自然言語でルールを考える（2 分）

コンソールの NL2Cedar に渡す文章を用意します。今回のルールはこれです。

> **ルール（日本語）**: OAuth ユーザーには天気ツール（get_weather）の呼び出しだけを許可する。それ以外はデフォルト拒否のまま。
>
> **英語で入力する例**:
> `Allow OAuth users to call the get_weather tool on this gateway. Do not permit any other tools.`

### 講義ポイント
- **「誰が(principal) / 何を(action) / どんな条件で(when)」** を明確に。曖昧な主語（「処理を許可」など）は生成精度を落とす
- 生成 AI は Gateway のツールスキーマ（ターゲット名・ツール名）を参照して action 名を埋めてくれる

---

## Step 3: NL2Cedar でポリシーを生成する（5 分）

コンソールのポリシーオーサリング機能で、自然言語 → Cedar 変換を行います。

1. Step 1 で作成したポリシーエンジンの詳細画面を開く
2. **Create policy**（ポリシーの作成）をクリック
3. オーサリング方法として **Natural language**（自然言語）を選択
   - あわせて対象 **Gateway** を選ぶ（ツールコンテキストの参照に必要）
4. テキスト欄に Step 2 の英語文を入力:
   ```
   Allow OAuth users to call the get_weather tool on this gateway.
   Do not permit any other tools.
   ```
5. **Generate**（生成）をクリック
6. 生成された Cedar 案を確認する。おおむね次のような内容になります:
   ```cedar
   permit(
       principal is AgentCore::OAuthUser,
       action == AgentCore::Action::"WeatherTarget___get_weather",
       resource == AgentCore::Gateway::"<あなたの gateway-arn>"
   );
   ```
7. 内容が意図どおりか目視レビューし、名前を付けて保存する:
   - **Policy name**: `allow-weather-tool`
   - このあと Step 4 で **LOG_ONLY** にするため、可能なら **enforcement mode: LOG_ONLY** を選択（選べない場合は Step 4 で変更）

### 講義ポイント
- **生成された案（アセット）は 7 日で自動削除**される。期間内に必ずポリシーとして保存すること
- 生成結果は**鵜呑みにしない**。特に action 名（ターゲット名）と Gateway ARN が正しいかを必ず確認
- Cedar は**ワイルドカード不可**なので、resource には具体的な Gateway ARN が入る

---

## Step 4: LOG_ONLY で安全に観察する（5 分）

いきなり本番適用（ENFORCE / ACTIVE）せず、まず **LOG_ONLY** で「もし有効化したら何が起きるか」を影響なしで観察します。

AgentCore の enforcement mode は **2 階層**あります。デモではエンジン単位で切り替えるのが分かりやすいです。

| レイヤー | 設定名 | 値 | 意味 |
|:--|:--|:--|:--|
| **ポリシーエンジン**（Gateway 紐付け時） | `mode` | `ENFORCE` / `LOG_ONLY` | エンジン全体。`LOG_ONLY` なら**どのポリシーも拒否しない**（優先される）|
| **個々のポリシー** | `enforcementMode` | `ACTIVE` / `LOG_ONLY` | 単一ポリシーだけ影のテスト |

### 手順（エンジンを LOG_ONLY で Gateway に紐付け）

1. AgentCore コンソールで対象の **Gateway** 詳細画面を開く
2. **Policy engine**（ポリシーエンジン）の設定を **Edit**（編集）
3. Step 1 のポリシーエンジンを選択し、**Enforcement mode** を **LOG_ONLY** にする
4. 保存する

これで Gateway 経由のツール呼び出しは評価されますが、**実際にはブロックされません**（ログのみ）。

### 動作テスト

Gateway 経由のエージェント（`demo/src/agent_with_gateway.py` など）から次を実行します。

- `get_weather` を呼ぶ → 判定は **permit**（ログ上）
- `get_schedule` を呼ぶ → 判定は **deny**（ログ上。ただし LOG_ONLY なので実際には通る）

### 判定結果の確認（Observability）

1. Gateway でトレーシングを有効にしておく
2. **CloudWatch** → **GenAI Observability**（または AgentCore Observability）を開く
3. ポリシー評価のスパン／メトリクスで、どのポリシーがマッチしたか、
   もし ACTIVE だったら **判定が反転していたか（decision-flipping）** を確認

### 講義ポイント
- **LOG_ONLY = 評価はするが拒否はしない**。本番トラフィックへの影響ゼロで検証できる
- 「このポリシーを ENFORCE にしたら何件ブロックされるか」を事前に数字で把握してから昇格できる
- エンジン単位 LOG_ONLY は「全ポリシーをまとめて観察」、ポリシー単位 LOG_ONLY は「新しい 1 本だけ影テスト」に向く

---

## Step 5（任意）: ENFORCE に昇格する

LOG_ONLY で十分に観察できたら、実際に許可/拒否を効かせます。

1. Gateway 詳細画面 → Policy engine 設定を **Edit**
2. **Enforcement mode** を **ENFORCE** に変更して保存
3. （個々のポリシーを絞る場合は、ポリシー側の enforcement mode を **ACTIVE** に）

これで `get_schedule` の呼び出しは実際にブロックされるようになります（deny-by-default + 天気のみ permit のため）。

---

## 片付け（クリーンアップ）

デモ後は課金・混乱を避けるため、逆順で削除します。

1. Gateway の Policy engine 紐付けを解除（または Enforcement mode を外す）
2. ポリシーエンジン内の **ポリシー**を削除
3. **ポリシーエンジン**を削除

> Gateway 自体を残しておけば、次回のデモですぐ再利用できます。

---

## まとめ

| Step | やったこと | キーワード |
|:--|:--|:--|
| 0-1 | Gateway ARN 確認 → ポリシーエンジン作成 | デフォルト拒否 |
| 2 | 自然言語でルールを記述 | principal / action / when |
| 3 | NL2Cedar で Cedar を生成・レビュー | ワイルドカード不可 / 7 日で失効 |
| 4 | LOG_ONLY で安全に観察 | 影響ゼロの事前検証 / 2 階層の mode |
| 5 | ENFORCE に昇格 | 本番適用 |

**「自然言語で書く → 生成をレビュー → LOG_ONLY で検証 → ENFORCE」** が
AgentCore Policy の推奨ワークフローです。

---

## 付録: CLI で同じことをやる場合（参考）

デモはコンソール中心ですが、再現やスクリプト化には AgentCore CLI が便利です。CLI は Gateway デプロイ後に `--generate` で NL2Cedar を呼べます。

```bash
# 1) プロジェクトに Gateway とポリシーエンジンを追加（LOG_ONLY で紐付け）
agentcore add policy-engine --name handson-policy-engine \
  --attach-to-gateways <YOUR_GATEWAY> \
  --attach-mode LOG_ONLY

# 2) Gateway をデプロイして ARN を確定（--generate は Gateway ARN を必要とするため）
agentcore deploy
agentcore status   # ここで Gateway ARN を確認

# 3) 自然言語から Cedar を生成してポリシー追加（NL2Cedar）
agentcore add policy --name allow-weather-tool \
  --engine handson-policy-engine \
  --generate "Allow OAuth users to call the get_weather tool. Do not permit any other tools." \
  --gateway <YOUR_GATEWAY>
agentcore deploy

# 4) 観察後、ENFORCE へ昇格する場合はエンジンの attach-mode を ENFORCE に更新して再デプロイ
```

AWS CLI（低レベル API）で行う場合は、Gateway 作成/更新時に `--policy-engine-configuration '{"arn":"<engine-arn>","mode":"LOG_ONLY"}'` を指定し、ポリシーは `aws bedrock-agentcore-control create-policy`（`--enforcement-mode LOG_ONLY`）、NL2Cedar は `aws bedrock-agentcore-control start-policy-generation` を使います。

> ⚠️ コンソールの画面名・ボタン名は更新される場合があります。実行前に最新の
> [AWS 公式ドキュメント](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy.html) を確認してください。

## 参考リンク

- [Getting started with Policy in AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy-getting-started.html)
- [Test a policy in LOG_ONLY mode](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy-test-a-policy.html)
- [Writing policies in natural language (NL2Cedar)](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy-natural-language.html)
- [StartPolicyGeneration API リファレンス](https://docs.aws.amazon.com/bedrock-agentcore-control/latest/APIReference/API_StartPolicyGeneration.html)
- [AWSブログ: Secure AI agents with Policy in AgentCore](https://aws.amazon.com/blogs/machine-learning/secure-ai-agents-with-policy-in-amazon-bedrock-agentcore/)
- [AgentCore_Policy_and_Cedar.md（本モジュールの解説ドキュメント）](./AgentCore_Policy_and_Cedar.md)
