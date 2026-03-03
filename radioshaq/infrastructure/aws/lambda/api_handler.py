"""
Lambda handler for SHAKODS API (API Gateway REST).
Handles /orchestrate and health; JWT auth; optionally starts Step Functions.
"""

from __future__ import annotations

import json
import os
from typing import Any

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver, Response
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext

from radioshaq.auth.jwt import JWTAuthManager, JWTConfig, TokenPayload, AuthenticationError

tracer = Tracer()
logger = Logger()
app = APIGatewayRestResolver()


def _get_auth_manager() -> JWTAuthManager:
    secret = os.environ.get("JWT_SECRET", "dev-secret-change-in-production")
    expire = int(os.environ.get("JWT_EXPIRE_MINUTES", "30"))
    config = JWTConfig(secret_key=secret, access_token_expire_minutes=expire)
    return JWTAuthManager(config=config)


def _start_orchestrator_workflow(request: str, context: dict[str, Any]) -> str | None:
    """Start Step Functions REACT orchestrator; return execution ARN or None if not configured."""
    state_machine_arn = os.environ.get("STEP_FUNCTIONS_ORCHESTRATOR_ARN")
    if not state_machine_arn:
        return None
    # State machine input: request, context, and Lambda ARN to invoke (from env or current function)
    orchestrator_arn = os.environ.get("ORCHESTRATOR_LAMBDA_ARN") or os.environ.get("AWS_LAMBDA_FUNCTION_ARN")
    payload = {"request": request, "context": context}
    if orchestrator_arn:
        payload["orchestratorFunctionArn"] = orchestrator_arn
    try:
        import boto3
        client = boto3.client("stepfunctions")
        execution = client.start_execution(
            stateMachineArn=state_machine_arn,
            input=json.dumps(payload),
        )
        return execution.get("executionArn")
    except Exception as e:
        logger.warning("Step Functions start failed", extra={"error": str(e)})
        return None


@app.get("/health")
@tracer.capture_lambda_handler
def health() -> dict[str, Any]:
    """Health check (no auth)."""
    return {"status": "ok", "service": "radioshaq-api"}


@app.post("/orchestrate")
@tracer.capture_lambda_handler
def orchestrate_request() -> Response:
    """Main orchestration endpoint: JWT auth, then start REACT workflow or return accepted."""
    body = app.current_event.json_body or {}
    auth_header = app.current_event.get_header_value("Authorization") or ""
    token = auth_header.replace("Bearer ", "").strip() if "Bearer " in auth_header else None

    if not token:
        return Response(status_code=401, body=json.dumps({"error": "Missing token"}), content_type="application/json")

    auth_manager = _get_auth_manager()
    try:
        payload: TokenPayload = auth_manager.verify_token(token)
    except AuthenticationError as e:
        return Response(status_code=401, body=json.dumps({"error": str(e)}), content_type="application/json")

    request_text = body.get("request") or ""
    context = {
        "user_id": payload.sub,
        "role": payload.role,
        "station_id": payload.station_id or "",
        **(body.get("context") or {}),
    }

    execution_arn = _start_orchestrator_workflow(request_text, context)
    if execution_arn:
        return Response(
            status_code=202,
            body=json.dumps({"execution_arn": execution_arn, "status": "started"}),
            content_type="application/json",
        )
    return Response(
        status_code=202,
        body=json.dumps({"status": "accepted", "message": "Orchestration requested (Step Functions not configured)."}),
        content_type="application/json",
    )


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
def lambda_handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    return app.resolve(event, context)
