from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .fetch import SubscriptionError
from .runtime import Runtime

ROOT = Path(__file__).resolve().parent.parent
VERSION = (ROOT / "VERSION").read_text("utf-8").strip()
COOKIE = "mihomo_session"
SESSION_AGE = 8 * 3600


class Login(BaseModel):
    username: str = Field(max_length=128)
    password: str = Field(max_length=1024)


class ProfileInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    url: str = Field(default="", max_length=4096)
    content: str = Field(default="", max_length=8 * 1024 * 1024)
    interval: int = Field(default=24, ge=0, le=720)


class NodeInput(BaseModel):
    name: str = Field(min_length=1, max_length=160)


class ProfileNodeInput(NodeInput):
    revision: str = Field(pattern=r"^[0-9a-f]{24}$")


def create_app(runtime: Runtime | None = None) -> FastAPI:
    username = os.getenv("MIHOMO_ADMIN_USERNAME", "admin")
    password_file = os.getenv("MIHOMO_ADMIN_PASSWORD_FILE")
    password = Path(password_file).read_text("utf-8").strip() if password_file else os.getenv("MIHOMO_ADMIN_PASSWORD", "")
    if len(password) < 12 or not username or any(ord(c) < 32 for c in username):
        raise RuntimeError("请设置至少 12 位的 MIHOMO_ADMIN_PASSWORD 和有效的管理员用户名")
    origin = os.getenv("PUBLIC_ORIGIN", "").rstrip("/")
    if origin and (urlsplit(origin).scheme not in {"http", "https"} or urlsplit(origin).path):
        raise RuntimeError("PUBLIC_ORIGIN 必须是后台访问地址，例如 https://proxy.example.com")
    secure_cookie = os.getenv("COOKIE_SECURE", "true").lower() == "true"
    runtime = runtime or Runtime(Path(os.getenv("DATA_DIR", "/data")).resolve(), os.getenv("MIHOMO_BINARY", "/usr/local/bin/mihomo"))
    signing_key = hashlib.sha256((runtime.private_key(".session-secret") + password).encode()).digest()
    failures = {}
    auth_lock = threading.Lock()

    @asynccontextmanager
    async def lifespan(app):
        runtime.start()
        try:
            yield
        finally:
            runtime.close()

    app = FastAPI(title="Mihomo 订阅管理", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)

    @app.middleware("http")
    async def limits(request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            if request.headers.get("X-Manager-Request") != "1":
                return JSONResponse({"detail": "请求校验失败，请从管理后台操作"}, status_code=403)
            received_origin = request.headers.get("Origin")
            expected = origin or str(request.base_url).rstrip("/")
            if received_origin and received_origin != expected:
                return JSONResponse({"detail": "访问域名与 PUBLIC_ORIGIN 不一致"}, status_code=403)
            body = bytearray()
            async for block in request.stream():
                body.extend(block)
                if len(body) > 9 * 1024 * 1024:
                    return JSONResponse({"detail": "请求内容过大"}, status_code=413)
            request._body = bytes(body)
        response = await call_next(request)
        response.headers.update({
            "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'",
        })
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(SubscriptionError)
    async def safe_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, exc):
        # Validation responses must not echo credential-bearing URLs or YAML.
        return JSONResponse({"detail": "输入不符合要求，请检查名称、链接和更新间隔"}, status_code=422)

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        return JSONResponse({"detail": "操作失败，已保留原有配置；请检查数据目录权限或服务状态"}, status_code=500)

    def authenticate(request: Request):
        try:
            value, signature = request.cookies.get(COOKIE, "").split(".", 1)
            expected = hmac.new(signing_key, value.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise ValueError
            issued, user, nonce = base64.urlsafe_b64decode(value).decode().split("\n")
            if user != username or not 0 <= time.time() - int(issued) < SESSION_AGE:
                raise ValueError
        except Exception:
            raise HTTPException(status_code=401, detail="请登录管理后台") from None

    @app.get("/health")
    def health():
        try:
            runtime._core("GET", "/version")
            return {"status": "ok"}
        except SubscriptionError:
            return JSONResponse({"status": "unavailable"}, status_code=503)

    @app.post("/api/login")
    def login(payload: Login, request: Request, response: Response):
        peer = request.client.host if request.client else "unknown"
        now = time.time()
        with auth_lock:
            for key in list(failures):
                if now - failures[key][0] > 600:
                    failures.pop(key, None)
            attempts = failures.get(peer, (now, 0))
            if attempts[1] >= 10:
                raise HTTPException(status_code=429, detail="登录尝试过多，请 10 分钟后重试")
            if not (hmac.compare_digest(payload.username.encode(), username.encode())
                    and hmac.compare_digest(payload.password.encode(), password.encode())):
                failures[peer] = (attempts[0], attempts[1] + 1)
                raise HTTPException(status_code=401, detail="用户名或密码错误")
            failures.pop(peer, None)
        value = base64.urlsafe_b64encode(f"{int(now)}\n{username}\n{secrets.token_hex(16)}".encode()).decode()
        signature = hmac.new(signing_key, value.encode(), hashlib.sha256).hexdigest()
        response.set_cookie(COOKIE, value + "." + signature, max_age=SESSION_AGE, httponly=True,
                            secure=secure_cookie, samesite="strict", path="/")
        return {"ok": True}

    @app.post("/api/logout")
    def logout(response: Response):
        response.delete_cookie(COOKIE, path="/", secure=secure_cookie, httponly=True, samesite="strict")
        return {"ok": True}

    @app.get("/api/overview", dependencies=[Depends(authenticate)])
    def overview():
        return {"version": VERSION, **runtime.overview()}

    def clean_name(value):
        value = value.strip()
        if not value or any(ord(c) < 32 for c in value):
            raise SubscriptionError("请填写有效的订阅名称")
        return value

    @app.post("/api/profiles", dependencies=[Depends(authenticate)])
    def add(payload: ProfileInput):
        runtime.add(clean_name(payload.name), payload.url.strip(), payload.content, payload.interval)
        return {"ok": True, "message": "订阅已添加；首个订阅自动启用"}

    @app.put("/api/profiles/{profile_id}", dependencies=[Depends(authenticate)])
    def edit(profile_id: str, payload: ProfileInput):
        runtime.edit(profile_id, clean_name(payload.name), payload.url.strip(), payload.interval)
        return {"ok": True, "message": "订阅已保存"}

    @app.post("/api/profiles/{profile_id}/refresh", dependencies=[Depends(authenticate)])
    def refresh(profile_id: str):
        runtime.refresh(profile_id)
        return {"ok": True, "message": "订阅已更新"}

    @app.post("/api/profiles/{profile_id}/activate", dependencies=[Depends(authenticate)])
    def activate(profile_id: str):
        runtime.activate(profile_id)
        return {"ok": True, "message": "订阅已切换"}

    @app.delete("/api/profiles/{profile_id}", dependencies=[Depends(authenticate)])
    def delete(profile_id: str):
        runtime.delete(profile_id)
        return {"ok": True, "message": "订阅已删除"}

    @app.put("/api/nodes/selected", dependencies=[Depends(authenticate)])
    def select(payload: NodeInput):
        runtime.select(payload.name)
        return {"ok": True, "message": "出口节点已切换"}

    @app.get("/api/profiles/{profile_id}/nodes", dependencies=[Depends(authenticate)])
    def profile_nodes(profile_id: str):
        return runtime.profile_nodes(profile_id)

    @app.post("/api/profiles/{profile_id}/nodes/delay", dependencies=[Depends(authenticate)])
    def profile_delay(profile_id: str, payload: ProfileNodeInput):
        return runtime.profile_delay(profile_id, payload.name, payload.revision)

    @app.post("/api/nodes/delay", dependencies=[Depends(authenticate)])
    def delay(payload: NodeInput):
        return {"delay": runtime.delay(payload.name)}

    assets = ROOT / "web" / "dist"
    if assets.exists():
        app.mount("/", StaticFiles(directory=assets, html=True), name="web")
    return app
