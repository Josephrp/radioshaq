"""JWT authentication for remote receiver (verify token from HQ)."""

from __future__ import annotations

import os
from typing import Any

import jwt
from pydantic import BaseModel


class ReceiverTokenPayload(BaseModel):
    """Decoded JWT claims for receiver."""

    sub: str
    role: str
    station_id: str | None = None
    scopes: list[str] = []


class JWTReceiverAuth:
    """Verify JWT tokens issued by RadioShaq HQ for receiver stations."""

    def __init__(self, secret: str | None = None, algorithm: str = "HS256"):
        self.secret = secret or os.environ.get("JWT_SECRET", "")
        self.algorithm = algorithm

    async def verify_token(self, token: str) -> ReceiverTokenPayload:
        """Verify and decode a JWT token. Raises on invalid/expired."""
        if not self.secret:
            raise ValueError("JWT_SECRET not configured")
        try:
            payload: Any = jwt.decode(
                token,
                self.secret,
                algorithms=[self.algorithm],
            )
            return ReceiverTokenPayload(
                sub=payload["sub"],
                role=payload.get("role", "receiver"),
                station_id=payload.get("station_id"),
                scopes=payload.get("scopes", []),
            )
        except jwt.ExpiredSignatureError:
            raise PermissionError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise PermissionError(f"Invalid token: {e}")
