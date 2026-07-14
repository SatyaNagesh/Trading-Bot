"""Auth & API Gateway — JWT auth, API key management, rate limiting."""

from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any, Callable

import jwt
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from packages.core.logging import setup_logging, get_logger

setup_logging()
logger = get_logger("auth_gateway")

app = FastAPI(title="QuantLab Auth Gateway", version="0.1.0")
security = HTTPBearer()

SECRET_KEY = "dev-secret-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

api_keys: dict[str, str] = {}
rate_limits: dict[str, list[datetime]] = {}
RATE_LIMIT = 60
RATE_WINDOW_SECONDS = 60


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_auth(func: Callable) -> Callable:
    @wraps(func)
    async def wrapper(request: Request, *args: Any, **kwargs: Any):
        auth: HTTPAuthorizationCredentials | None = await security(request)
        if not auth:
            raise HTTPException(status_code=401, detail="Missing auth header")
        payload = verify_token(auth.credentials)
        request.state.user = payload.get("sub")
        return await func(request, *args, **kwargs)
    return wrapper


@app.get("/health")
async def health():
    return {"status": "ok", "service": "auth-gateway"}


@app.post("/auth/token")
async def login(username: str, password: str):
    if username == "admin" and password == "admin":
        token = create_access_token(username)
        return {"access_token": token, "token_type": "bearer"}
    raise HTTPException(status_code=401, detail="Invalid credentials")


@app.post("/auth/api-key")
async def generate_api_key(request: Request, name: str):
    from uuid import uuid4
    key = str(uuid4())
    api_keys[name] = key
    logger.info("api_key_generated", name=name)
    return {"name": name, "api_key": key}


@app.get("/auth/api-keys")
async def list_api_keys():
    return api_keys


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next: Callable):
    client_ip = request.client.host if request.client else "unknown"
    now = datetime.now(timezone.utc)
    if client_ip not in rate_limits:
        rate_limits[client_ip] = []
    rate_limits[client_ip] = [
        t for t in rate_limits[client_ip]
        if (now - t).total_seconds() < RATE_WINDOW_SECONDS
    ]
    rate_limits[client_ip].append(now)
    if len(rate_limits[client_ip]) > RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    return await call_next(request)
