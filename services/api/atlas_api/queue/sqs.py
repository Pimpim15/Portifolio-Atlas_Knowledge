"""Helper utilities to interact with SQS."""

from __future__ import annotations

from functools import lru_cache
from typing import Any
from urllib.parse import urlparse

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from ..config import get_settings
from ..observability.logging import get_logger

logger = get_logger(component="api", module="queue.sqs")


@lru_cache(maxsize=1)
def get_sqs_client() -> Any:
    settings = get_settings()
    kwargs: dict[str, Any] = {
        "region_name": settings.aws_region,
    }

    if settings.aws_access_key_id and settings.aws_secret_access_key:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key

    if settings.aws_endpoint_url:
        kwargs["endpoint_url"] = settings.aws_endpoint_url

    return boto3.client("sqs", **kwargs)


def ensure_queue_exists(queue_url: str | None = None) -> None:
    settings = get_settings()
    target_url = queue_url or settings.sqs_queue_url
    if not target_url:
        return

    client = get_sqs_client()
    try:
        client.get_queue_attributes(QueueUrl=target_url, AttributeNames=["QueueArn"])
        return
    except client.exceptions.QueueDoesNotExist:
        parsed = urlparse(target_url)
        queue_name = parsed.path.rsplit("/", 1)[-1]
        try:
            client.create_queue(QueueName=queue_name)
        except (BotoCoreError, ClientError) as exc:  # pragma: no cover - infra failure
            logger.exception("sqs_create_queue_failed", queue_name=queue_name, error=str(exc))
    except (BotoCoreError, ClientError) as exc:  # pragma: no cover - infra failure
        logger.exception("sqs_get_queue_attributes_failed", queue_url=target_url, error=str(exc))
