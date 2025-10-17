"""Unit tests for structured logging masking."""

from __future__ import annotations

import json
import logging

from services.api.atlas_api.observability.logging import configure_logging, get_logger


def test_logging_masks_pii(caplog) -> None:
    configure_logging()
    logger = get_logger(component="test")
    with caplog.at_level(logging.INFO):
        logger.info("auth_attempt", email="user@example.com", access_token="secret")
    assert caplog.records, "expected one log record"
    payload = json.loads(caplog.records[-1].message)
    assert payload["email"] == "***redacted***"
    assert payload["access_token"] == "***redacted***"
