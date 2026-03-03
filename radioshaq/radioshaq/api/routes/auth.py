"""Authentication endpoints: token issue and refresh."""

from fastapi import APIRouter, Depends, HTTPException

from radioshaq.api.dependencies import get_auth_manager, get_current_user
from radioshaq.auth.jwt import JWTAuthManager, TokenPayload

router = APIRouter()


@router.post("/token")
async def create_token(
    subject: str,
    role: str = "field",
    station_id: str | None = None,
    auth_manager: JWTAuthManager = Depends(get_auth_manager),
) -> dict[str, str]:
    """Create an access token (e.g. for field station)."""
    token = auth_manager.create_access_token(
        subject=subject,
        role=role,
        station_id=station_id,
    )
    return {"access_token": token, "token_type": "bearer"}


@router.post("/refresh")
async def refresh_token(
    refresh_token: str,
    auth_manager: JWTAuthManager = Depends(get_auth_manager),
) -> dict[str, str]:
    """Exchange refresh token for new access token."""
    try:
        token = auth_manager.refresh_access_token(refresh_token)
        return {"access_token": token, "token_type": "bearer"}
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/me", response_model=dict)
async def me(
    payload: TokenPayload = Depends(get_current_user),
) -> dict:
    """Return current token claims (requires Bearer token)."""
    return {
        "sub": payload.sub,
        "role": payload.role,
        "station_id": payload.station_id,
        "scopes": payload.scopes,
    }
