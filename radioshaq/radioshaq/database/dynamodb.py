"""DynamoDB state store for serverless deployment.

Stores REACT orchestrator session state in DynamoDB for use with Lambda
or when Postgres is not available.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError
from loguru import logger


class DynamoDBStateStore:
    """
    Store and retrieve session state in DynamoDB.
    Compatible with the same interface as PostGISManager.save_session_state / get_session_state.
    """

    def __init__(
        self,
        table_name: str,
        region_name: str = "us-east-1",
        endpoint_url: str | None = None,
    ):
        self.table_name = table_name
        self._client = boto3.client(
            "dynamodb",
            region_name=region_name,
            endpoint_url=endpoint_url,
        )
        self._resource = boto3.resource(
            "dynamodb",
            region_name=region_name,
            endpoint_url=endpoint_url,
        )
        self._table = self._resource.Table(table_name)

    async def save_session_state(
        self,
        session_id: str,
        task_id: str,
        phase: str,
        state_data: dict,
        status: str = "active",
    ) -> None:
        """Save REACT session state (session_id is partition key)."""
        now = datetime.now(timezone.utc).isoformat()
        item = {
            "session_id": session_id,
            "task_id": task_id,
            "phase": phase,
            "state_data": _serialize(state_data),
            "status": status,
            "updated_at": now,
            "created_at": now,
        }

        def _put() -> None:
            self._table.put_item(Item=item)

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _put)

    async def get_session_state(self, session_id: str) -> dict[str, Any] | None:
        """Retrieve session state by session_id."""

        def _get() -> dict | None:
            try:
                resp = self._table.get_item(Key={"session_id": session_id})
            except ClientError as e:
                logger.warning("DynamoDB get_session_state failed: %s", e)
                return None
            return resp.get("Item")

        loop = asyncio.get_running_loop()
        item = await loop.run_in_executor(None, _get)
        if not item:
            return None
        state_data = item.get("state_data")
        if isinstance(state_data, str):
            try:
                state_data = json.loads(state_data)
            except json.JSONDecodeError:
                state_data = {}
        return {
            "session_id": item["session_id"],
            "task_id": item.get("task_id", ""),
            "phase": item.get("phase", ""),
            "state_data": state_data or {},
            "status": item.get("status", "active"),
            "created_at": item.get("created_at"),
            "updated_at": item.get("updated_at"),
        }


def _serialize(data: dict) -> str:
    """Serialize state_data for DynamoDB (store as string for nested dicts)."""
    return json.dumps(data, default=str)
