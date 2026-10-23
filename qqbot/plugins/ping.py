from nonebot import on_command
from nonebot.plugin import PluginMetadata

from qqbot.rules import permitted
from qqbot.runtime import get_runtime

__plugin_meta__ = PluginMetadata(name="连接检查", description="检查机器人连接", usage="/测试连接")
matcher = on_command("测试连接", rule=permitted("ping"), priority=10, block=True)


@matcher.handle()
async def reply():
    await matcher.finish(get_runtime().store.get("ping").options["reply_text"])
