"""Resolve a handler's plugin, effective options and contextual logger."""
from dataclasses import dataclass

from nonebot import logger
from nonebot.adapters.onebot.v11 import Event
from nonebot.matcher import Matcher
from pydantic import BaseModel

from .catalog import CATALOG
from .runtime import get_runtime


def managed_plugin_id(matcher: Matcher) -> str | None:
    modules = {spec.module: key for key, spec in CATALOG.items()}
    plugin = matcher.plugin
    while plugin is not None:
        if plugin.module_name in modules:
            return modules[plugin.module_name]
        plugin = plugin.parent_plugin
    return None


@dataclass(frozen=True)
class PluginContext:
    plugin_id: str
    group_id: str | None
    user_id: str | None
    options: BaseModel
    logger: object


def plugin_context(event: Event, matcher: Matcher) -> PluginContext:
    plugin_id = managed_plugin_id(matcher)
    if plugin_id is None:
        raise ValueError("此响应器未声明为受管理插件")
    group = getattr(event, "group_id", None)
    user = getattr(event, "user_id", None)
    group_id = str(group) if group is not None else None
    user_id = str(user) if user is not None else None
    prefix = f"plugin={plugin_id} group={group_id or '-'} user={user_id or '-'}"

    def annotate(record):
        record["message"] = f"{prefix} {record['message']}"

    return PluginContext(plugin_id, group_id, user_id,
                         get_runtime().store.resolve_options(plugin_id, group_id),
                         logger.patch(annotate))
