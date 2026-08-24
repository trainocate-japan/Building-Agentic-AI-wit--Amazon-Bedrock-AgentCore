# MCPサーバーの自己記述性 — 説明はサーバー側に用意しなくて良い？

## 結論

MCPサーバーに別途ドキュメントファイルを用意する必要はありません。MCPのプロトコル自体が「サーバーが何をできるか」を自動的に伝える仕組みを持っています。

## MCPの自己記述メカニズム

### 1. ツールの docstring がそのまま説明になる

```python
@mcp.tool()
def add_numbers(a: int, b: int) -> int:
    """2 つの数字を足す"""  # ← これがクライアントに渡る説明
    return a + b
```

### 2. 型ヒントがスキーマになる

`a: int, b: int` → JSON Schema として公開され、引数の型・必須/任意がクライアントに自動伝達されます。

### 3. `tools/list` エンドポイント

MCPクライアントが接続時に自動で `tools/list` を呼び、全ツールの名前・説明・パラメータスキーマを取得します。

## クライアント側のコードに説明は不要

```python
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def main():
    mcp_url = "http://localhost:8000/mcp"
    headers = {}

    async with streamablehttp_client(mcp_url, headers, timeout=120,
        terminate_on_close=False) as (
        read_stream, write_stream, _,
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tool_result = await session.list_tools()
            print(tool_result)

asyncio.run(main())
```

このコードは「サーバーに何ができるか聞いている」側なので、説明を持っていなくて当然です。

## `list_tools()` の戻り値例

```json
{
  "tools": [
    {
      "name": "add_numbers",
      "description": "2 つの数字を足す",
      "inputSchema": {
        "type": "object",
        "properties": {
          "a": {"type": "integer"},
          "b": {"type": "integer"}
        },
        "required": ["a", "b"]
      }
    }
  ]
}
```

## 通信フロー

```
クライアント                         サーバー
    |                                  |
    |-- session.initialize() --------->|
    |                                  |
    |-- session.list_tools() --------->|
    |                                  |
    |<-- ツール一覧（名前・説明・スキーマ）--|
    |                                  |
    |-- session.call_tool(...) ------->|
    |<-- 実行結果 ----------------------|
```

## まとめ

| 側 | 説明が必要？ | 理由 |
|---|---|---|
| **サーバー** | docstring と型ヒントを書く | これがそのままツール定義としてクライアントに渡る |
| **クライアント** | 不要 | サーバーから自動取得する仕組み |

## とはいえ、用意した方が良い場面

| 場面 | 対策 |
|---|---|
| 人間の開発者向け | README.md に使い方・セットアップ手順を書く |
| 複雑なツール | docstring を充実させる（引数の意味、戻り値の形式、使用例） |
| ツール間の使い分け | サーバー名やツール名を分かりやすくする |

## docstring の改善例

```python
@mcp.tool()
def add_numbers(a: int, b: int) -> int:
    """2つの整数を加算して結果を返す。
    
    Args:
        a: 1つ目の整数
        b: 2つ目の整数
    
    Returns:
        a + b の結果
    """
    return a + b
```

docstring を詳細に書くほど、LLMがツールを正しく選択・使用できる確率が上がります。特にツール数が多い場合は、説明の質がそのままエージェントの精度に直結します。
