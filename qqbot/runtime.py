from datetime import datetime, timezone

from .catalog import CATALOG
from .albums import AlbumStore
from .settings import PluginStore


class Runtime:
    def __init__(self, store: PluginStore):
        self.store = store
        self.albums = AlbumStore(store.path.parent / "albums")
        self.loaded: set[str] = set()
        self.load_errors: dict[str, str] = {}
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.startup_load = {key: store.get(key).load_on_start for key in CATALOG}

    def decision(self, plugin_id: str, group_id: str | None,
                 user_id: str | None = None, *, group_event: bool = False) -> dict:
        settings = self.store.get(plugin_id)
        if plugin_id not in self.loaded:
            reason = "插件尚未加载" if plugin_id not in self.load_errors else "插件加载失败"
        elif not settings.enabled:
            reason = "插件功能已关闭"
        elif group_id is not None:
            if group_id not in settings.group_ids:
                reason = "该群不在插件白名单中"
            elif (not group_event and group_id in settings.group_user_ids
                  and user_id not in settings.group_user_ids[group_id]):
                reason = "该用户不在此群的插件白名单中"
            else:
                return {"allowed": True, "reason": "该群和用户符合插件权限"}
        elif not settings.allow_private:
            reason = "插件未开放私聊"
        elif settings.private_user_ids is not None and user_id not in settings.private_user_ids:
            reason = "该用户不在插件私聊白名单中"
        else:
            return {"allowed": True, "reason": "该用户符合插件私聊权限"}
        return {"allowed": False, "reason": reason}

    def allowed(self, plugin_id: str, group_id: str | None,
                user_id: str | None = None) -> bool:
        return self.decision(plugin_id, group_id, user_id)["allowed"]

    def plugin_status(self, plugin_id: str) -> dict:
        spec = CATALOG[plugin_id]
        settings = self.store.get(plugin_id)
        loaded = plugin_id in self.loaded
        return {
            "id": plugin_id, "name": spec.name, "description": spec.description,
            "commands": spec.commands, "settings": settings.model_dump(),
            "loaded": loaded, "load_error": self.load_errors.get(plugin_id),
            "load_state": "failed" if plugin_id in self.load_errors else ("loaded" if loaded else "not_loaded"),
            "restart_required": settings.load_on_start != self.startup_load[plugin_id],
            "options_schema": spec.options_model.model_json_schema(),
        }


_runtime: Runtime | None = None


def set_runtime(runtime: Runtime) -> None:
    global _runtime
    _runtime = runtime


def get_runtime() -> Runtime:
    if _runtime is None:
        raise RuntimeError("机器人运行环境尚未初始化")
    return _runtime
