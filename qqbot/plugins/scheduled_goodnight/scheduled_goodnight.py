import asyncio
from contextlib import suppress
from datetime import datetime, timezone

from nonebot import get_bots, get_driver, logger
from nonebot.adapters.onebot.v11 import Bot
from nonebot.plugin import PluginMetadata

from qqbot.runtime import get_runtime
from .core import GoodnightSender
from .spec import SPEC

__plugin_meta__ = PluginMetadata(name=SPEC.name, description=SPEC.description,
                                usage="在管理页配置群范围、北京时间、文案和图集。")
task: asyncio.Task | None = None


async def run_schedule() -> None:
    sender = GoodnightSender(get_runtime())
    while True:
        try:
            bot = next((bot for bot in get_bots().values() if isinstance(bot, Bot)), None)
            await sender.tick(datetime.now(timezone.utc), bot)
        except Exception as exc:
            logger.error("plugin={} event=scheduled outcome=error error={}", SPEC.id, type(exc).__name__)
        await asyncio.sleep(5)


@get_driver().on_startup
async def start_schedule() -> None:
    global task
    task = asyncio.create_task(run_schedule())


@get_driver().on_shutdown
async def stop_schedule() -> None:
    if task is not None:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
