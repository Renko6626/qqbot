from nonebot import on_command
from nonebot.params import Depends
from nonebot.plugin import PluginMetadata

from qqbot.context import PluginContext, plugin_context

from .spec import SPEC

__plugin_meta__ = PluginMetadata(name=SPEC.name, description=SPEC.description, usage="/示例")
matcher = on_command("示例", priority=10, block=True)


@matcher.handle()
async def reply(context: PluginContext = Depends(plugin_context, use_cache=False)):
    # Host checks authorization and resolves public + group options automatically.
    # use_cache=False prevents sharing a plugin context with another matcher.
    context.logger.info("准备回复")
    await matcher.finish(context.options.reply_text)
