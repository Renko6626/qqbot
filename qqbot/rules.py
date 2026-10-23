from nonebot.adapters.onebot.v11 import MessageEvent, GroupMessageEvent

from .runtime import get_runtime


def permitted(plugin_id: str):
    async def check(event: MessageEvent) -> bool:
        group_id = str(event.group_id) if isinstance(event, GroupMessageEvent) else None
        return get_runtime().allowed(plugin_id, group_id)
    return check
