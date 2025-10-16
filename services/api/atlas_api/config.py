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
    opensearch_endpoint: str = Field("http://localhost:9200", alias="OPENSEARCH_ENDPOINT")
    sqs_queue_url: str | None = Field(None, alias="SQS_QUEUE_URL")
    aws_region: str = Field("us-east-1", alias="AWS_REGION")
    aws_access_key_id: str | None = Field(None, alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str | None = Field(None, alias="AWS_SECRET_ACCESS_KEY")
    aws_endpoint_url: str | None = Field(None, alias="AWS_ENDPOINT_URL")

    jwt_issuer: str = Field("atlas-knowledge", alias="JWT_ISSUER")
    jwt_audience: list[str] = Field(default_factory=lambda: ["atlas-api"], alias="JWT_AUDIENCE")
    jwt_public_key: str = Field(
        (
            "-----BEGIN PUBLIC KEY-----\n"
            "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAqYXrez83hSEoy9cBS0Zj\n"
            "uxpx+ZnC2DYLRZ82k7fZ0Lzr1sZ/+b6kn/PFdobtFgqUJb60U1nvyFTjcsxl/lPB\n"
            "UMeODhtdL9HfM+8KfQZRJJF0fVudP7CrlTO8+fhD3GTvdBrzEmbDorDe/0qnBHKn\n"
            "t0BAg0J7b04YJ4D/k9vlJoVcWMkGyu0xU1h2HJ7DLUoXnOv8rXKYvHQ5VVcUHFO+\n"
            "fgeOS0y5d4+wFGKsl6zO8Fax+kBKjI+HgqwInfVcEAJZlddwEkMk5+lETLgCCFuy\n"
            "1zsZpDe5xCWUiqkY1zjIlkNnj89fHwD9vY2otcjd0a3oL0hNEhmz92ukIG8xJ5WY\n"
            "EwIDAQAB\n"
            "-----END PUBLIC KEY-----"
        ),
        alias="JWT_PUBLIC_KEY",
    )
    jwt_private_key: str = Field(
        (
            "-----BEGIN PRIVATE KEY-----\n"
            "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCphet7PzeFISjL\n"
            "1wFLRmO7GnH5mcLYNgtFnzaTt9nQvOvWxn/5vqSf88V2hu0WCpQlvrRTWe/IVONy\n"
            "zGX+U8FQx44OG10v0d8z7wp9BlEkkXR9W50/sKuVM7z5+EPcZO90GvMSZsOisN7/\n"
            "SqcEcqe3QECDQntvThgngP+T2+UmhVxYyQbK7TFTWHYcnsMtShec6/ytcpi8dDlV\n"
            "VxQcU75+B45LTLl3j7AUYqyXrM7wVrH6QEqMj4eCrAid9VwQAlmV13ASQyTn6URM\n"
            "uAIIW7LXOxmkN7nEJZSKqRjXOMiWQ2ePz18fAP29jai1yN3RregvSE0SGbP3a6Qg\n"
            "bzEnlZgTAgMBAAECggEAM2cIIDbq/tMvK5/mJI0TcIh0Rtr42daJVHMSeXgl88VV\n"
            "Paqy42eLQ3UHSwlemnBau5c31o5Oxs/2p7iStKtw0q2vxVdGylk49OZmp8JimFQC\n"
            "noBJDibj4Dnv81v0N7/jW7FQQyQl7g7zjzVzr0WU1VwGM8bU5ssnR9M1q//hW+xU\n"
            "/Zw1ftErb54xtgxNMWGojzOs3CwLbWgWn/ct7zDCfPFIc6RH2RPhN8FUrvEHOA+f\n"
            "+AEcrSqQkhF1CXkGWt8WNhMoHQEgYMhHqBZXnih8Fw/W4wLxUySjPcF/2+elEa3d\n"
            "JwENWM0sSa8BrJC+6bJwwInalDtHzLH/AAAy8RsCAQKBgQDqW75gEDuiyaz9EfaO\n"
            "XliR+mgr9iLykyPv200LHMDOGCO2G3TaBW1hFyi/QDLpc/YOoPFNcoMjEkyjLsuq\n"
            "PdRfAAzascNRueeZJS1KC+I2I0qCrOE8nSxVPuR1U2fYEPqX3rBFBZ4amyD9H2aE\n"
            "wRCPZC4YJbBY2jWJZnePhGibewKBgQC5LXbS5yEkK44v0I6bEsV9lci1t2cMexj+\n"
            "wgDJbnugP0wSP8Gria/HoAcPwpWkpbgiodk7/YK74HmwHVvIpmmIiOQqZibQroNq\n"
            "OOG0bJogx5LU+KdwFp0HnOsB82+jhKDW1+UgXKbXTB8F7LeIizz0X/1ptvOBwwLW\n"
            "ECKsIfcmSQKBgHHYN1a7C/08MwiMnVTzh9sB5XDVlIx55c8ynO50/UQgfdiM5eqz\n"
            "EDtF4MlnClRVvIXGsPGKWyHCVfA/XzhH6M5tW9Ew4UzmHhdK9AEwXKcn5Z4tFQ04\n"
            "3LxcXOaRqbRQKytzRfWBkRgjm5balhaPIthFNg8M3+mJttAUMqhJDffZAoGAYKuY\n"
            "XY+loIFQcCu7Vr9c9CvOpPbCyCQ3Lz/OM1oHFegVaW15SHjPmDI1nYeioVqWHxZJ\n"
            "FuVIa5ZLUKJy+PPPIiT8oBnF56lDF5/sTElpyPUG9UF9/6j+fyvvD4yrWjzxzlbU\n"
            "2akkvD6T737dbV3rC1RVMev9gV9xypiP0TbGFGkCgYEAtLeOWRWBVMPqGAXmY4iY\n"
            "h/MyTYvK1bLZGEGCfTudyRtN0YKEwnE8f3slD7X2x73spp4YpNP4ORj3HDGGxGiQ\n"
            "qII4pqNdHpon5HuCuGZnyx0u5xevO7GHsnL6x3CQi1IbXqF2Ep512y8yo1S/DD5E\n"
            "weIFyvvGeTwvWQkipIER490=\n"
            "-----END PRIVATE KEY-----"
        ),
        alias="JWT_PRIVATE_KEY",
    )
    jwt_algorithm: str = Field("RS256", alias="JWT_ALGORITHM")
    access_token_ttl_minutes: int = Field(15, alias="ACCESS_TOKEN_TTL")
    refresh_token_ttl_minutes: int = Field(60 * 24 * 7, alias="REFRESH_TOKEN_TTL")

    rate_limit_default: str = Field("60/minute", alias="RATE_LIMIT_DEFAULT")
    rate_limit_auth: str = Field("10/minute", alias="RATE_LIMIT_AUTH")
    rate_limit_mutation: str = Field("30/minute", alias="RATE_LIMIT_MUTATION")

    opentelemetry_endpoint: str | None = Field(None, alias="OTEL_EXPORTER_OTLP_ENDPOINT")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retorna configuração cacheada."""

    return Settings()  # type: ignore[call-arg]
