"""
Lambda handler for SHAKODS message ingestion (e.g. SQS, API Gateway webhook).
Processes incoming messages (WhatsApp, SMS, etc.) and forwards to HQ API when
RADIOSHAQ_HQ_URL is set. Expects body with InboundMessage-compatible fields:
channel, sender_id, chat_id, content; optional media, metadata.
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

logger = Logger()
tracer = Tracer()

# When set, POST each message to {HQ_URL}/internal/bus/inbound (nanobot MessageBus).
HQ_URL = os.environ.get("RADIOSHAQ_HQ_URL", "").rstrip("/")


def _forward_to_hq(payload: dict[str, Any]) -> bool:
    """POST payload to HQ /internal/bus/inbound. Returns True if accepted."""
    if not HQ_URL:
        return False
    url = f"{HQ_URL}/internal/bus/inbound"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return 200 <= resp.status < 300
    except Exception as e:
        logger.warning("HQ forward failed: %s", e)
        return False


def _process_record(record: dict[str, Any]) -> bool:
    """Process a single message record (SQS or direct invoke payload). Returns True if processed."""
    body = record.get("body")
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            body = {"raw": body}
    if not body:
        return False
    channel = body.get("channel", "unknown")
    logger.info("Message received", extra={"channel": channel, "body_keys": list(body.keys())})

    # InboundMessage-compatible payload for HQ bus
    payload = {
        "channel": body.get("channel", "api"),
        "sender_id": body.get("sender_id", ""),
        "chat_id": body.get("chat_id", ""),
        "content": body.get("content", body.get("message", body.get("text", ""))),
        "media": body.get("media", []),
        "metadata": body.get("metadata", {}),
    }
    if HQ_URL:
        _forward_to_hq(payload)
    return True


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    """Handle SQS batch or single message payload."""
    records = event.get("Records", [event]) if "Records" in event else [event]
    batch_item_failures: list[dict[str, str]] = []
    for i, record in enumerate(records):
        try:
            if not _process_record(record):
                batch_item_failures.append({"itemIdentifier": record.get("messageId", str(i))})
        except Exception as e:
            logger.exception("Record processing failed", extra={"record_index": i})
            batch_item_failures.append({"itemIdentifier": record.get("messageId", str(i))})

    if batch_item_failures and "Records" in event:
        return {"batchItemFailures": batch_item_failures}
    return {"statusCode": 200, "processed": len(records) - len(batch_item_failures)}
