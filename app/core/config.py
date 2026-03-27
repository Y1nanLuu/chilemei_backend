from functools import lru_cache
from pathlib import Path

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    project_name: str = "Chilemei Backend"
    api_v1_prefix: str = "/api/v1"
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = "123456"
    mysql_db: str = "chilemei"
    mysql_charset: str = "utf8mb4"
    secret_key: str = "replace-this-with-a-long-random-secret"
    access_token_expire_minutes: int = 60 * 24 * 7
    auto_create_tables: bool = False
    wechat_app_id: str = ""
    wechat_app_secret: str = ""
    wechat_code2session_url: str = "https://api.weixin.qq.com/sns/jscode2session"
    media_dir: str = "media"
    food_record_upload_dir: str = "food_records"
    media_url_prefix: str = "/media"

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}"
            f"?charset={self.mysql_charset}"
        )

    @property
    def media_root(self) -> Path:
        return Path(self.media_dir)

    @property
    def food_record_media_root(self) -> Path:
        return self.media_root / self.food_record_upload_dir


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
