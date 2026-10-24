import secrets
from collections.abc import Callable
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import ValidationError
from starlette.responses import Response

from .catalog import CATALOG
from .album_api import register_album_routes
from .runtime import Runtime
from .settings import GroupId, PluginSettings, UserId

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
                   password: str, coolify_url: str,
                   restart: Callable[[], None] | None = None) -> None:
    if not username or not password:
        raise ValueError("必须设置 BOT_ADMIN_USER 和 BOT_ADMIN_PASSWORD")
    basic = HTTPBasic()

    def authenticated(credentials: HTTPBasicCredentials = Depends(basic)):
        user_ok = secrets.compare_digest(credentials.username.encode(), username.encode())
        password_ok = secrets.compare_digest(credentials.password.encode(), password.encode())
        if not (user_ok and password_ok):
            raise HTTPException(401, "账号或密码不正确", headers={"WWW-Authenticate": 'Basic realm="QQ Bot"'})

    router = APIRouter(dependencies=[Depends(authenticated)])

    def check_write(request: Request):
        if request.headers.get("X-Requested-With") != "qqbot-admin":
            raise HTTPException(403, "请从管理页提交操作")

    @router.get("/")
    async def page():
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-store"})

    @router.get("/assets/{name}")
    async def asset(name: str):
        if name not in {"admin.css", "admin.js", "forms.js", "albums.js"}:
            raise HTTPException(404)
        return FileResponse(STATIC / name, headers={"Cache-Control": "no-store"})

    @router.get("/api/status")
    async def status():
        import nonebot
        bots = nonebot.get_bots()
        return {"started_at": runtime.started_at, "connected_accounts": sorted(bots),
                "coolify_url": coolify_url, "process_restart_supported": restart is not None}

    @router.get("/api/plugins")
    async def plugins():
        return [runtime.plugin_status(plugin_id) for plugin_id in CATALOG]

    @router.get("/api/plugins/{plugin_id}/permission")
    async def permission(plugin_id: str, user_id: UserId, group_id: GroupId | None = None):
        if plugin_id not in CATALOG:
            raise HTTPException(404, "插件不存在")
        return runtime.decision(plugin_id, group_id, user_id)

    @router.post("/api/restart", status_code=202, dependencies=[Depends(check_write)])
    async def process_restart(background: BackgroundTasks):
        if restart is None:
            raise HTTPException(503, "此运行环境未启用进程重启，请到 Coolify 操作")
        background.add_task(restart)
        return {"message": "正在重启 NoneBot 进程", "started_at": runtime.started_at}

    @router.put("/api/plugins/{plugin_id}", dependencies=[Depends(check_write)])
    async def save(plugin_id: str, settings: PluginSettings, request: Request):
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

    register_album_routes(router, runtime.albums, check_write)
    app.include_router(router)
    app.add_middleware(AdminRoutesOnly)
