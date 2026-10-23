from nonebot.adapters.onebot.v11 import Event, GroupMessageEvent, PrivateMessageEvent
from nonebot.exception import IgnoredException
from nonebot.matcher import Matcher
from nonebot.message import run_preprocessor

from .catalog import CATALOG
from .runtime import get_runtime


def event_allowed(plugin_id: str, event: Event) -> bool:
    runtime = get_runtime()
    if isinstance(event, GroupMessageEvent):
        return runtime.allowed(plugin_id, str(event.group_id), str(event.user_id))
    if isinstance(event, PrivateMessageEvent):
        return runtime.allowed(plugin_id, None, str(event.user_id))
    group_id = getattr(event, "group_id", None)
    if event.get_type() in {"notice", "request"} and group_id is not None:
        return runtime.decision(plugin_id, str(group_id), group_event=True)["allowed"]
    return False


async def enforce_plugin_policy(event: Event, matcher: Matcher) -> None:
    plugin = matcher.plugin
    modules = {spec.module: key for key, spec in CATALOG.items()}
    while plugin is not None:
        plugin_id = modules.get(plugin.module_name)
        if plugin_id is not None:
            if not event_allowed(plugin_id, event):
                raise IgnoredException("插件未启用或当前会话不在白名单中")
            return
        plugin = plugin.parent_plugin


def install_policy() -> None:
    run_preprocessor(enforce_plugin_policy)
