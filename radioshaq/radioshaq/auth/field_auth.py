"""Field station authentication and token exchange."""

from __future__ import annotations

from radioshaq.auth.jwt import JWTAuthManager, TokenPayload
from radioshaq.config.schema import Config as ShakodsConfig
from radioshaq.config.schema import JWTConfig


class FieldAuthManager:
    """
    Field station authentication: issue and verify short-lived tokens
    for field stations (callsign/station_id).
    """

    def __init__(
        self,
        jwt_manager: JWTAuthManager | None = None,
        config: JWTConfig | None = None,
    ):
        if config is None:
            try:
                config = ShakodsConfig().jwt
            except Exception:
                config = JWTConfig()
        self.jwt = jwt_manager or JWTAuthManager(config=config)

    def create_field_token(
        self,
        station_id: str,
        subject: str | None = None,
        scopes: list[str] | None = None,
    ) -> str:
        """
        Create a short-lived token for a field station.
        station_id is typically the callsign.
        """
        sub = subject or station_id
        return self.jwt.create_access_token(
            subject=sub,
            role="field",
            station_id=station_id,
            scopes=scopes or ["field", "basic"],
        )

    def verify_field_token(self, token: str) -> TokenPayload:
        """Verify a field station token; raises AuthenticationError if invalid."""
        payload = self.jwt.verify_token(token)
        if payload.role != "field":
            from radioshaq.auth.jwt import AuthenticationError
            raise AuthenticationError("Token is not a field station token")
        return payload

    def exchange_for_access_token(
        self,
        station_id: str,
        existing_token: str | None = None,
    ) -> str:
        """
        Issue a new field access token.
        If existing_token is provided and valid (e.g. refresh), re-issue from its claims.
        Otherwise issue fresh token for station_id.
        """
        if existing_token:
            try:
                payload = self.jwt.verify_token(existing_token)
                if payload.role == "field" and (payload.station_id == station_id or payload.sub == station_id):
                    return self.jwt.create_access_token(
                        subject=payload.sub,
                        role="field",
                        station_id=payload.station_id or station_id,
                        scopes=[s for s in payload.scopes if s != "refresh"],
                    )
            except Exception:
                pass
        return self.create_field_token(station_id)
