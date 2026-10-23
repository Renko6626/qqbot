from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent, GroupMessageEvent
from nonebot.plugin import PluginMetadata

from qqbot.catalog import CATALOG
from qqbot.runtime import get_runtime

__plugin_meta__ = PluginMetadata(name="帮助", description="查看可用指令", usage="/帮助")
matcher = on_command("帮助", priority=10, block=True)


@matcher.handle()
async def reply(event: MessageEvent):
    runtime = get_runtime()
    group_id = str(event.group_id) if isinstance(event, GroupMessageEvent) else None
    lines = [f"{spec.name}：{'、'.join(spec.commands)}" for key, spec in CATALOG.items()
             if runtime.allowed(key, group_id, str(event.user_id))]
    await matcher.finish("当前可用指令\n" + "\n".join(lines))
