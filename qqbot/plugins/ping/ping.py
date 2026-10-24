from nonebot import on_command
from nonebot.plugin import PluginMetadata
from nonebot.params import Depends

from qqbot.context import PluginContext, plugin_context

__plugin_meta__ = PluginMetadata(name="连接检查", description="检查机器人连接", usage="/测试连接")
matcher = on_command("测试连接", priority=10, block=True)


@matcher.handle()
async def reply(context: PluginContext = Depends(plugin_context, use_cache=False)):
    await matcher.finish(context.options.reply_text)
