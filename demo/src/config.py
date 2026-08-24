"""設定管理モジュール

SSM Parameter Store からシステムプロンプトなどの設定を取得します。
パラメータストアを使うことで:
  - 再デプロイなしでプロンプトを変更可能
  - バージョン履歴が自動で残る
  - 複数エージェント間で設定を共有可能
"""

import os

import boto3
from botocore.exceptions import ClientError

# ========================================
# パラメータストアのキー設計
# ========================================
# /agentcore/{agent-name}/system-prompt   - システムプロンプト
# /agentcore/{agent-name}/model-id        - モデルID

PARAMETER_PREFIX = os.environ.get(
    "PARAMETER_PREFIX", "/agentcore/secretary-agent"
)
REGION = os.environ.get("AWS_REGION", "us-east-1")

# ========================================
# フォールバック用デフォルト値
# ========================================
DEFAULT_SYSTEM_PROMPT = """あなたは優秀な秘書エージェントです。名前は「セクレタリー」です。

以下の方針で行動してください:
- 簡潔で正確な情報を提供する
- 日本語で応答する
- 不明な点があれば確認を取る
- ユーザーの時間を無駄にしない

あなたは研修講師の秘書として、スケジュール管理や情報収集を支援します。
"""

DEFAULT_MODEL_ID = "us.amazon.nova-pro-v1:0"


def _get_ssm_client():
    """SSM クライアントを取得する。"""
    return boto3.client("ssm", region_name=REGION)


def get_parameter(name: str, default: str = "") -> str:
    """SSM Parameter Store からパラメータを取得する。

    取得に失敗した場合はデフォルト値を返す（デモ環境でのフォールバック）。

    Args:
        name: パラメータのフルパス (例: /agentcore/secretary-agent/system-prompt)
        default: 取得失敗時のデフォルト値

    Returns:
        パラメータの値
    """
    try:
        ssm = _get_ssm_client()
        response = ssm.get_parameter(Name=name, WithDecryption=True)
        return response["Parameter"]["Value"]
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "ParameterNotFound":
            print(f"  ⚠️  パラメータ未登録: {name} → デフォルト値を使用")
        else:
            print(f"  ⚠️  パラメータ取得エラー ({error_code}): {name} → デフォルト値を使用")
        return default
    except Exception as e:
        print(f"  ⚠️  SSM 接続エラー: {e} → デフォルト値を使用")
        return default


def get_system_prompt() -> str:
    """システムプロンプトを取得する。"""
    return get_parameter(
        f"{PARAMETER_PREFIX}/system-prompt",
        default=DEFAULT_SYSTEM_PROMPT,
    )


def get_model_id() -> str:
    """モデル ID を取得する。"""
    return get_parameter(
        f"{PARAMETER_PREFIX}/model-id",
        default=DEFAULT_MODEL_ID,
    )
