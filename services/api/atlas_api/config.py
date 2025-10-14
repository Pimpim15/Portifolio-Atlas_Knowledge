"""Configurações da aplicação."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    environment: Literal["local", "dev", "prod"] = "local"
    debug: bool = False

    database_url: str = Field("sqlite+aiosqlite:///./atlas.db", alias="DATABASE_URL")
    redis_url: str = Field("redis://localhost:6379/0", alias="REDIS_URL")
    opensearch_endpoint: str = Field("https://localhost:9200", alias="OPENSEARCH_ENDPOINT")
    sqs_queue_url: str | None = Field(None, alias="SQS_QUEUE_URL")

    jwt_issuer: str = Field("atlas-knowledge", alias="JWT_ISSUER")
    jwt_audience: list[str] = Field(default_factory=lambda: ["atlas-api"], alias="JWT_AUDIENCE")
    jwt_public_key: str = Field(
        (
            "-----BEGIN PUBLIC KEY-----\n"
            "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAvZrOt1\n"
            "sUAf9S1t9xXxM1Eh5ZL9W86w7ksg6\n"
            "-----END PUBLIC KEY-----"
        ),
        alias="JWT_PUBLIC_KEY",
    )
    jwt_private_key: str = Field(
        (
            "-----BEGIN PRIVATE KEY-----\n"
            "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCAmMwggJfAgEAAoGBAL1\n"
            "fake-dev-key\n"
            "-----END PRIVATE KEY-----"
        ),
        alias="JWT_PRIVATE_KEY",
    )
    jwt_algorithm: str = Field("RS256", alias="JWT_ALGORITHM")
    access_token_ttl_minutes: int = Field(15, alias="ACCESS_TOKEN_TTL")
    refresh_token_ttl_minutes: int = Field(60 * 24 * 7, alias="REFRESH_TOKEN_TTL")

    rate_limit_default: str = Field("60/minute", alias="RATE_LIMIT_DEFAULT")
    rate_limit_auth: str = Field("10/minute", alias="RATE_LIMIT_AUTH")

    opentelemetry_endpoint: str | None = Field(None, alias="OTEL_EXPORTER_OTLP_ENDPOINT")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retorna configuração cacheada."""

    return Settings()  # type: ignore[call-arg]
