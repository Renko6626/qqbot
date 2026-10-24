"""One daily attempt per permitted group; no persistent scheduling state."""
from datetime import date, datetime, timedelta, timezone
from time import perf_counter

import anyio
from nonebot import logger
from nonebot.adapters.onebot.v11 import Bot, Message, MessageSegment

from qqbot.runtime import Runtime
from .spec import SPEC

BEIJING = timezone(timedelta(hours=8))


class GoodnightSender:
    def __init__(self, runtime: Runtime):
        self.runtime = runtime
        self.day: date | None = None
        self.attempted: set[str] = set()

    async def tick(self, now: datetime, bot: Bot | None) -> None:
        local = now.astimezone(BEIJING)
        if self.day != local.date():
            self.day = local.date()
            self.attempted.clear()
        if bot is None:
            return
        runtime = self.runtime
        for group in runtime.store.get(SPEC.id).group_ids:
            if group in self.attempted or not self._allowed(group):
                continue
            options = runtime.store.resolve_options(SPEC.id, group)
            if options.time != local.strftime("%H:%M"):
                continue
            self.attempted.add(group)
            started = perf_counter()
            try:
                message = Message()
                if options.text:
                    message += MessageSegment.text(options.text)
                try:
                    def read_image():
                        path = runtime.albums.random_image(options.album)
                        return path.read_bytes() if path else None

                    data = await anyio.to_thread.run_sync(read_image)
                    if data is not None:
                        message += MessageSegment.image(data)
                except (OSError, ValueError) as exc:
                    logger.warning("plugin={} group={} event=scheduled outcome=image_unavailable error={}",
                                   SPEC.id, group, type(exc).__name__)
                if not message or not self._allowed(group):
                    logger.info("plugin={} group={} event=scheduled outcome=skipped", SPEC.id, group)
                    continue
                await bot.send_group_msg(group_id=int(group), message=message)
                logger.info("plugin={} group={} user=- event=scheduled outcome=sent elapsed_ms={}",
                            SPEC.id, group, round((perf_counter() - started) * 1000))
            except Exception as exc:
                logger.error("plugin={} group={} user=- event=scheduled outcome=error elapsed_ms={} error={}",
                             SPEC.id, group, round((perf_counter() - started) * 1000), type(exc).__name__)

    def _allowed(self, group: str) -> bool:
        return self.runtime.decision(SPEC.id, group, group_event=True)["allowed"]
