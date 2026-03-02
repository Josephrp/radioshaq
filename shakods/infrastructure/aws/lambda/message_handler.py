"""
Lambda handler for SHAKODS message ingestion (e.g. SQS, API Gateway webhook).
Processes incoming messages (WhatsApp, SMS, etc.) and enqueues for orchestration.
"""

from __future__ import annotations

import json
import os
from typing import Any

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

logger = Logger()
tracer = Tracer()


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
    # Placeholder: forward to orchestrator / SNS / Step Functions as needed
    channel = body.get("channel", "unknown")
    logger.info("Message received", extra={"channel": channel, "body_keys": list(body.keys())})
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
