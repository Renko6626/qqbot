from time import perf_counter

from nonebot import logger
from nonebot.adapters.onebot.v11 import Event, GroupMessageEvent, PrivateMessageEvent
from nonebot.exception import IgnoredException
from nonebot.matcher import Matcher
from nonebot.message import run_postprocessor, run_preprocessor

from .context import managed_plugin_id
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


def log_execution(plugin_id: str, event: Event, outcome: str, elapsed_ms: int = 0,
                  exception: Exception | None = None) -> None:
    # Never include event bodies, download URLs or exception messages here.
    logger.log("ERROR" if exception else "INFO",
               "plugin={} group={} user={} event={} outcome={} elapsed_ms={} error={}",
               plugin_id, getattr(event, "group_id", "-"), getattr(event, "user_id", "-"),
               event.get_type(), outcome, elapsed_ms, type(exception).__name__ if exception else "-")


async def enforce_plugin_policy(event: Event, matcher: Matcher) -> None:
    plugin_id = managed_plugin_id(matcher)
    if plugin_id is None:
        return
    if not event_allowed(plugin_id, event):
        log_execution(plugin_id, event, "denied")
        raise IgnoredException("插件未启用或当前会话不在白名单中")
    matcher._qqbot_started = perf_counter()


async def record_plugin_execution(event: Event, matcher: Matcher,
                                  exception: Exception | None) -> None:
    plugin_id = managed_plugin_id(matcher)
    if plugin_id is None:
        return
    started = getattr(matcher, "_qqbot_started", perf_counter())
    log_execution(plugin_id, event, "error" if exception else "completed",
                  round((perf_counter() - started) * 1000), exception)


def install_policy() -> None:
    run_preprocessor(enforce_plugin_policy)
    run_postprocessor(record_plugin_execution)
