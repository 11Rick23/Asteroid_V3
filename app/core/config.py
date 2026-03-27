import os
from logging import getLogger

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from ruamel.yaml import YAML

logger = getLogger(__name__)

_config: AsteroidConfig | None = None


class AsteroidConfig(BaseModel):
    """小惑星の設定を保持するクラス。"""

    model_config = ConfigDict(extra="forbid")

    # BOTを起動するためのトークン
    DISCORD_BOT_TOKEN: str

    # 読み込むモジュール
    MODULE_LIST: dict[str, bool] = Field(default_factory=lambda: {"AUTH": True})

    # ==== ログ設定 ====
    # デバッグログファイルの保存日数
    DEBUG_LOG_RETENTION_DAYS: int = 7

    # 警告ログファイルの保存日数
    WARNING_LOG_RETENTION_DAYS: int = 7

    @classmethod
    def load(cls) -> AsteroidConfig:
        """config.yaml および環境変数から設定を読み込む。"""

        logger.debug("設定を読み込みます。")

        # config.yamlを読み込む
        yaml = YAML(typ="safe")
        with open("config.yaml", encoding="utf-8") as f:
            yaml_data = yaml.load(f) or {}
        data = dict(yaml_data)

        logger.debug("config.yamlの内容を読み込みました。")

        if not data:
            logger.warning("config.yamlが空です。")

        # .envファイルを読み込む
        load_dotenv()

        # 環境変数を上書きする形で読み込む
        for field_name in cls.model_fields:
            if field_name in os.environ:
                data[field_name] = os.environ[field_name]

        logger.debug("環境変数の内容を読み込みました。")

        # Pydanticのバリデーションを通す
        try:
            return cls.model_validate(data)
        except ValidationError as e:
            logger.error(f"設定の読み込みに失敗しました: \n {e}")
            raise RuntimeError(f"設定の読み込みに失敗しました: \n {e}") from e


def get_config() -> AsteroidConfig:
    """AsteroidConfigのインスタンスを取得する。"""
    global _config
    if _config is None:
        _config = AsteroidConfig.load()
    return _config


def reload_config() -> AsteroidConfig:
    """AsteroidConfigのインスタンスを再読み込みする。"""
    global _config
    _config = AsteroidConfig.load()
    return _config
