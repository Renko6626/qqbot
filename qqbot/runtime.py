from datetime import datetime, timezone

from .catalog import CATALOG
from .settings import PluginStore


class Runtime:
    def __init__(self, store: PluginStore):
        self.store = store
        self.loaded: set[str] = set()
        self.load_errors: dict[str, str] = {}
        self.started_at = datetime.now(timezone.utc).isoformat()

    def allowed(self, plugin_id: str, group_id: str | None) -> bool:
        settings = self.store.get(plugin_id)
        if plugin_id not in self.loaded or not settings.enabled:
            return False
        if group_id is None:
            return settings.allow_private
        return group_id in settings.group_ids

    def plugin_status(self, plugin_id: str) -> dict:
        spec = CATALOG[plugin_id]
        settings = self.store.get(plugin_id)
        loaded = plugin_id in self.loaded
        return {
            "id": plugin_id, "name": spec.name, "description": spec.description,
            "commands": spec.commands, "settings": settings.model_dump(),
            "loaded": loaded, "load_error": self.load_errors.get(plugin_id),
            "restart_required": settings.load_on_start != loaded,
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
