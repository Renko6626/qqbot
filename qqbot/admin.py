import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import ValidationError
from starlette.responses import Response

from .catalog import CATALOG
from .runtime import Runtime
from .settings import PluginSettings

STATIC = Path(__file__).parent / "static"


class AdminRoutesOnly:
    """Do not expose the adapter's unused inbound OneBot transports."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        if scope["type"] == "http" and scope["path"].startswith("/onebot/"):
            await Response(status_code=404)(scope, receive, send)
            return
        await self.app(scope, receive, send)


def register_admin(app: FastAPI, runtime: Runtime, username: str,
                   password: str, coolify_url: str) -> None:
    if not username or not password:
        raise ValueError("必须设置 BOT_ADMIN_USER 和 BOT_ADMIN_PASSWORD")
    basic = HTTPBasic()

    def authenticated(credentials: HTTPBasicCredentials = Depends(basic)):
        user_ok = secrets.compare_digest(credentials.username.encode(), username.encode())
        password_ok = secrets.compare_digest(credentials.password.encode(), password.encode())
        if not (user_ok and password_ok):
            raise HTTPException(401, "账号或密码不正确", headers={"WWW-Authenticate": 'Basic realm="QQ Bot"'})

    router = APIRouter(dependencies=[Depends(authenticated)])

    @router.get("/")
    async def page():
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-store"})

    @router.get("/assets/{name}")
    async def asset(name: str):
        if name not in {"admin.css", "admin.js"}:
            raise HTTPException(404)
        return FileResponse(STATIC / name, headers={"Cache-Control": "no-store"})

    @router.get("/api/status")
    async def status():
        import nonebot
        bots = nonebot.get_bots()
        return {"started_at": runtime.started_at, "connected_accounts": sorted(bots),
                "coolify_url": coolify_url}

    @router.get("/api/plugins")
    async def plugins():
        return [runtime.plugin_status(plugin_id) for plugin_id in CATALOG]

    @router.put("/api/plugins/{plugin_id}")
    async def save(plugin_id: str, settings: PluginSettings, request: Request):
        if request.headers.get("X-Requested-With") != "qqbot-admin":
            raise HTTPException(403, "请从管理页保存配置")
        if plugin_id not in CATALOG:
            raise HTTPException(404, "插件不存在")
        try:
            runtime.store.save(plugin_id, settings)
        except ValidationError:
            raise HTTPException(422, "插件参数不符合要求，请检查输入") from None
        except OSError:
            raise HTTPException(500, "配置保存失败，请查看 Coolify 日志和数据目录权限") from None
        return runtime.plugin_status(plugin_id)

    @app.get("/healthz")
    async def health():
        return {"status": "ok"}

    app.include_router(router)
    app.add_middleware(AdminRoutesOnly)
