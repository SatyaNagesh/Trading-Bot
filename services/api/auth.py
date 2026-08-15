"""Authentication — API-key-based middleware using configurable secret."""

import secrets
from typing import Any

from fastapi import HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from services.api.config import APIConfig

_security = HTTPBearer(auto_error=False)
_config: APIConfig | None = None


def configure_auth(config: APIConfig) -> None:
    global _config
    _config = config


async def verify_api_key(credentials: HTTPAuthorizationCredentials | None) -> str | None:
    if credentials is None:
        return None
    token = credentials.credentials
    if not _config:
        return None
    if not secrets.compare_digest(token, _config.api_secret):
        raise HTTPException(status_code=403, detail="Invalid API key")
    return token


async def require_auth(request: Request) -> str | None:
    credentials: HTTPAuthorizationCredentials | None = await _security(request)
    return await verify_api_key(credentials)


async def optional_auth(request: Request) -> str | None:
    credentials: HTTPAuthorizationCredentials | None = await _security(request)
    if credentials is None:
        return None
    try:
        return await verify_api_key(credentials)
    except HTTPException:
        return None
