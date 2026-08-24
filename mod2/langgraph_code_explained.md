# LangGraph コード解説

このスライドは、LangGraph を使ってエージェントを構築する基本パターンを示しています。大きく4つの要素を定義しています。

---

## 1. モデルの定義

```python
from langchain_aws import ChatBedrock

llm = ChatBedrock(model_id="")  # 希望するモデル
```

Amazon Bedrock 上のLLMを呼び出すクライアントを作成します。`model_id` に Claude や Titan などのモデルIDを指定します。

---

## 2. ツールのバインド

```python
tools = [calculator, weather]
llm_with_tools = llm.bind_tools(tools)
```

LLMに使わせたいツール（関数）をリストで渡し、`bind_tools` でモデルに紐づけます。これにより、LLMが「計算が必要」「天気を調べたい」と判断したとき、該当ツールを呼び出せるようになります。

---

## 3. システムメッセージとチャットボットノードの定義

```python
system_message = "You're a helpful assistant..."

def chatbot(state: MessagesState):
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}
```

- `system_message`: LLMの振る舞いを指示するプロンプト
- `chatbot` 関数: グラフ内の「ノード」として動作し、メッセージ履歴を受け取ってLLMを呼び出し、応答を返します

---

## 4. グラフの構築

```python
graph_builder = StateGraph(MessagesState)
graph_builder.add_node("chatbot", chatbot)
graph_builder.add_node("tools", ToolNode(tools))
```

`StateGraph` でグラフを初期化し、2つのノードを登録します:

- **chatbot**: LLMで応答を生成する
- **tools**: LLMがツール呼び出しを要求した場合に実行する

```python
graph_builder.add_conditional_edges("chatbot", tools_condition)
graph_builder.add_edge("tools", "chatbot")
```

エッジ（ノード間の接続）を定義します:

- **条件付きエッジ**: chatbot の出力を見て、ツール呼び出しが必要なら `tools` ノードへ、不要ならそのまま終了
- **通常エッジ**: tools の実行結果は必ず chatbot に戻る（ツール結果を踏まえて再度LLMが応答）

```python
graph_builder.set_entry_point("chatbot")
return graph_builder.compile()
```

エントリーポイント（最初に実行されるノード）を `chatbot` に設定し、グラフをコンパイルして完成です。

---

## 処理の流れまとめ

```
ユーザー入力 → chatbot(LLM) → ツール必要？
                                  ├─ Yes → tools実行 → chatbot に戻る
                                  └─ No  → 最終応答を返す
```

このループ構造により、LLMが必要に応じて何度でもツールを使い、最終的な回答を組み立てるエージェントが実現できます。
