from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    project_name: str = "Chilemei Backend"
    api_v1_prefix: str = "/api/v1"
    mysql_host: str = Field(default="127.0.0.1", validation_alias=AliasChoices("MYSQL_HOST", "DB_HOST"))
    mysql_port: int = Field(default=3306, validation_alias=AliasChoices("MYSQL_PORT", "DB_PORT"))
    mysql_user: str = Field(default="root", validation_alias=AliasChoices("MYSQL_USER", "DB_USER"))
    mysql_password: str = Field(
        default="123456",
        validation_alias=AliasChoices("MYSQL_PASSWORD", "DB_PASSWORD"),
    )
    mysql_db: str = Field(default="chilemei", validation_alias=AliasChoices("MYSQL_DB", "DB_NAME"))
    mysql_charset: str = Field(default="utf8mb4", validation_alias=AliasChoices("MYSQL_CHARSET", "DB_CHARSET"))
    secret_key: str = "replace-this-with-a-long-random-secret"
    access_token_expire_minutes: int = 60 * 24 * 7
    auto_create_tables: bool = False
    wechat_app_id: str = ""
    wechat_app_secret: str = ""
    wechat_code2session_url: str = "https://api.weixin.qq.com/sns/jscode2session"
    wechat_cos_getauth_url: str = "http://api.weixin.qq.com/_/cos/getauth"
    wechat_cos_meta_encode_url: str = "https://api.weixin.qq.com/_/cos/metaid/encode"
    storage_request_timeout: float = 10.0
    storage_root_dir: str = "media"
    food_upload_dir: str = "food"
    temp_upload_dir: str = "tmp"
    cos_bucket: str = ""
    cos_region: str = "ap-shanghai"
    cos_public_domain: str = ""
    cos_secret_id: str = ""
    cos_secret_key: str = ""
    cos_session_token: str = ""
    cos_scheme: str = "https"

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}"
            f"?charset={self.mysql_charset}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
