import os
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _env_file() -> str:
    explicit = os.getenv("ENV_FILE")
    if explicit:
        return explicit

    app_env = os.getenv("APP_ENV", "local")
    base_dir = Path(__file__).resolve().parent.parent.parent
    candidates = [
        base_dir / f".env.{app_env}",
        base_dir / ".env",
        Path(f".env.{app_env}"),
        Path(".env"),
        base_dir / "tests" / ".env",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_env_file(), env_file_encoding="utf-8-sig", extra="ignore")

    APP_ENV: str = "local"

    DB_USER: str = ""
    DB_PASSWORD: str = ""
    DB_HOST: str = "localhost"
    DB_PORT: str = "5432"
    DB_NAME: str = "gaji_market"

    JWT_SECRET: str = "dev-secret"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    # 로그인 유지기간 5주 — 이 값만큼 refresh token JWT의 exp와 Redis TTL이 같이 늘어난다
    # (security.create_refresh_token / redis_client.save_refresh_token 참고).
    REFRESH_TOKEN_EXPIRE_DAYS: int = 35

    FRONTEND_ORIGIN: str = "http://localhost:3000"
    FRONTEND_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
    FORBIDDEN_WORDS_PATH: str = ""

    REDIS_HOST: str = ""
    REDIS_PW: str = ""
    REDIS_URL: str = ""

    OAUTH_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/oauth/kakao/callback"
    KAKAO_CLIENT_ID: str = ""
    KAKAO_CLIENT_SECRET: str = ""
    KAKAO_REST_API_KEY: str = ""
    KAKAO_ADMIN_KEY: str = ""
    KAKAO_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/oauth/kakao/callback"
    NAVER_CLIENT_ID: str = ""
    NAVER_CLIENT_SECRET: str = ""
    NAVER_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/oauth/naver/callback"
    NAVER_MAPS_API_KEY_ID: str = ""
    NAVER_MAPS_API_KEY_SECRET: str = ""
    SEOUL_OPEN_DATA_API_KEY: str = ""
    SEOUL_OPEN_API_KEY: str = Field(default="", repr=False)
    SEOUL_CITYDATA_SERVICE: str = Field(default="", repr=False)
    SEOUL_OPEN_API_BASE_URL: str = "http://openapi.seoul.go.kr:8088"
    # Preserve existing deployments whose *_SERVICE variables contain API keys.
    SEOUL_BIKE_API_KEY: str = Field(default="", repr=False, validation_alias=AliasChoices("SEOUL_BIKE_API_KEY", "SEOUL_BIKE_SERVICE"))
    SEOUL_SUBWAY_API_KEY: str = Field(default="", repr=False, validation_alias=AliasChoices("SEOUL_SUBWAY_API_KEY", "SEOUL_SUBWAY_SERVICE", "SEOUL_SUBWAY_SERVIC"))
    SEOUL_CITYDATA_API_KEY: str = Field(default="", repr=False, validation_alias=AliasChoices("SEOUL_CITYDATA_API_KEY", "SEOUL_CITYDATA_SERVICE"))
    WEATHER_API_KEY: str = Field(default="", repr=False)
    AIR_KOREA_SERVICE_KEY: str = Field(default="", repr=False)
    OMNIROUTE_API_KEY: str = ""
    OMNIROUTE_BASE_URL: str = "http://localhost:20128/v1"
    OMNIROUTE_MODEL: str = "gpt 5.6"
    OMNIROUTE_FALLBACK_MODEL: str = "claude5.0"

    # NCP Object Storage (S3 호환) — 중고거래 상품 이미지 업로드용
    NCP_ACCESS_KEY: str = ""
    NCP_SECRET_KEY: str = ""
    NCP_BUCKET: str = ""
    NCP_ENDPOINT: str = "https://kr.object.ncloudstorage.com"
    NCP_REGION: str = "kr-standard"

    @property
    def database_url(self) -> str:
        if not self.DB_USER or not self.DB_PASSWORD:
            return "sqlite:///./local_dev.db"
        port = self.DB_PORT or "5432"
        if port == "6543":
            port = "5432"
        return (
            f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{port}/{self.DB_NAME}"
        )

    @property
    def redis_url(self) -> str:
        if self.REDIS_URL:
            return self.REDIS_URL
        if self.REDIS_HOST and self.REDIS_PW:
            return f"redis://:{self.REDIS_PW}@{self.REDIS_HOST}:6379/0"
        if self.REDIS_HOST:
            return f"redis://{self.REDIS_HOST}:6379/0"
        return ""

    @property
    def kakao_redirect_uri(self) -> str:
        return self.KAKAO_REDIRECT_URI or self.OAUTH_REDIRECT_URI

    @property
    def kakao_client_id(self) -> str:
        return self.KAKAO_CLIENT_ID or self.KAKAO_REST_API_KEY

    @property
    def naver_redirect_uri(self) -> str:
        return self.NAVER_REDIRECT_URI


settings = Settings()
