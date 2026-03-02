"""JWT authentication for SHAKODS distributed agents."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import jwt
from pydantic import BaseModel, Field as PydanticField

from shakods.config.schema import JWTConfig


class AuthenticationError(Exception):
    """Raised when token verification fails."""

    pass


class TokenPayload(BaseModel):
    """JWT token payload (claims)."""

    sub: str  # Subject (user/agent ID)
    role: str  # Role: field, hq, receiver
    station_id: str | None = None  # Ham radio callsign
    scopes: list[str] = PydanticField(default_factory=lambda: ["basic"])
    exp: int = 0  # Expiration (Unix timestamp)
    iat: int = 0  # Issued at (Unix timestamp)

    @property
    def is_expired(self) -> bool:
        """True if token has expired."""
        return datetime.now(timezone.utc).timestamp() > self.exp


class JWTAuthManager:
    """
    JWT authentication manager for SHAKODS distributed agents.
    Handles token generation, validation, and refresh.
    """

    def __init__(self, config: JWTConfig | None = None):
        self.config = config or JWTConfig()

    def create_access_token(
        self,
        subject: str,
        role: str,
        station_id: str | None = None,
        scopes: list[str] | None = None,
    ) -> str:
        """Create a new access token."""
        now = datetime.now(timezone.utc)
        expire = now.timestamp() + (self.config.access_token_expire_minutes * 60)
        payload = {
            "sub": subject,
            "role": role,
            "station_id": station_id,
            "scopes": scopes or ["basic"],
            "exp": int(expire),
            "iat": int(now.timestamp()),
        }
        return jwt.encode(
            payload,
            self.config.secret_key,
            algorithm=self.config.algorithm,
        )

    def create_refresh_token(
        self,
        subject: str,
        role: str,
        station_id: str | None = None,
    ) -> str:
        """Create a refresh token (longer-lived, has refresh scope)."""
        now = datetime.now(timezone.utc)
        expire_days = self.config.refresh_token_expire_days
        expire = now.timestamp() + (expire_days * 86400)
        payload = {
            "sub": subject,
            "role": role,
            "station_id": station_id,
            "scopes": ["refresh"],
            "exp": int(expire),
            "iat": int(now.timestamp()),
        }
        return jwt.encode(
            payload,
            self.config.secret_key,
            algorithm=self.config.algorithm,
        )

    def verify_token(self, token: str) -> TokenPayload:
        """Verify and decode a JWT token."""
        try:
            payload: Any = jwt.decode(
                token,
                self.config.secret_key,
                algorithms=[self.config.algorithm],
            )
            return TokenPayload(
                sub=payload["sub"],
                role=payload["role"],
                station_id=payload.get("station_id"),
                scopes=payload.get("scopes", ["basic"]),
                exp=int(payload["exp"]),
                iat=int(payload["iat"]),
            )
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise AuthenticationError(f"Invalid token: {e}")

    def refresh_access_token(self, refresh_token: str) -> str:
        """Create new access token from valid refresh token."""
        payload = self.verify_token(refresh_token)
        if "refresh" not in payload.scopes:
            raise AuthenticationError("Invalid refresh token")
        return self.create_access_token(
            subject=payload.sub,
            role=payload.role,
            station_id=payload.station_id,
            scopes=[s for s in payload.scopes if s != "refresh"],
        )
