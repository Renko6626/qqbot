import asyncio
import subprocess
import sys

import nonebot
import pytest
from nonebot.adapters.onebot.v11 import Adapter, Bot, GroupMessageEvent
from pydantic import ValidationError

from qqbot.catalog import CATALOG, NoOptions, PluginSpec
from qqbot.context import plugin_context
from qqbot.rules import enforce_plugin_policy
from qqbot.runtime import Runtime, set_runtime
from qqbot.settings import PluginSettings, PluginStore


def group_event(user_id=11111):
    return GroupMessageEvent.model_validate({
        "time": 0, "self_id": 10000, "post_type": "message", "message_type": "group",
        "sub_type": "normal", "message_id": 1, "group_id": 12345, "user_id": user_id,
        "anonymous": None, "message": "/测试连接", "raw_message": "/测试连接",
        "font": 0, "sender": {"user_id": user_id, "nickname": "tester"},
    })


def test_discovery_does_not_import_handlers():
    result = subprocess.run([sys.executable, "-c", """
import sys
from qqbot.catalog import CATALOG
assert {'ping','help','smart_mirror'} <= CATALOG.keys()
assert not any(spec.module in sys.modules for spec in CATALOG.values())
"""], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_sparse_group_options_inherit_and_keep_explicit_values(monkeypatch, tmp_path):
    class Options(NoOptions):
        count: int = 2
        enabled: bool = True
        labels: list[str] = ["default"]
        note: str | None = "public"

    monkeypatch.setitem(CATALOG, "sample", PluginSpec("sample", "Sample", "", (), Options))
    store = PluginStore(tmp_path / "plugins.json")
    settings = PluginSettings(group_ids=["12345"], options={"count": 7},
                              group_options={"12345": {"enabled": False, "labels": [], "note": None}})
    store.save("sample", settings)
    assert store.resolve_options("sample", "12345").model_dump() == {
        "count": 7, "enabled": False, "labels": [], "note": None}
    settings.options = {"count": 0}
    store.save("sample", settings)
    assert store.resolve_options("sample", "12345").count == 0
    restored = PluginStore(store.path)
    assert restored.get("sample").group_options == {
        "12345": {"enabled": False, "labels": [], "note": None}}
    assert restored.resolve_options("sample", None).enabled is True
    settings.group_options = {}
    store.save("sample", settings)
    assert store.resolve_options("sample", "12345").labels == ["default"]


def test_invalid_group_options_do_not_change_file_or_permissions(tmp_path):
    store = PluginStore(tmp_path / "plugins.json")
    store.save("ping", PluginSettings(enabled=True, group_ids=["12345"],
                                     group_user_ids={"12345": ["11111"]}))
    before = store.path.read_bytes()
    for override in [{"reply_text": ""}, {"unknown": 2}, {"reply_text": False}]:
        with pytest.raises(ValidationError):
            store.save("ping", PluginSettings(group_ids=["12345"],
                                              group_options={"12345": override}))
    assert store.path.read_bytes() == before
    with pytest.raises(ValidationError):
        PluginSettings(group_options={"99999": {"reply_text": "hi"}})
    runtime = Runtime(store)
    runtime.loaded.add("ping")
    assert not runtime.allowed("ping", "12345", "22222")


def test_handler_receives_group_parameters_via_nonebot_dependency(tmp_path):
    nonebot.init(driver="~none")
    plugin = nonebot.get_plugin("ping") or nonebot.load_plugin(CATALOG["ping"].module)
    matcher = next(iter(plugin.matcher))()
    runtime = Runtime(PluginStore(tmp_path / "plugins.json"))
    runtime.loaded.add("ping")
    runtime.store.save("ping", PluginSettings(enabled=True, group_ids=["12345"],
                                             options={"reply_text": "public"},
                                             group_options={"12345": {"reply_text": "group reply"}}))
    set_runtime(runtime)
    sent = []

    class CaptureBot(Bot):
        async def send(self, event, message, **kwargs):
            sent.append(str(message))
            return {"message_id": 1}

    bot = CaptureBot(Adapter(nonebot.get_driver()), "10000")
    event = group_event()
    asyncio.run(enforce_plugin_policy(event, matcher))
    asyncio.run(matcher.run(bot, event, {}))
    assert sent == ["group reply"]
    assert plugin_context(event, matcher).options.reply_text == "group reply"


def test_execution_log_has_plugin_result_without_message_or_exception_text(tmp_path):
    from nonebot import logger
    from qqbot.rules import record_plugin_execution

    nonebot.init(driver="~none")
    plugin = nonebot.get_plugin("ping") or nonebot.load_plugin(CATALOG["ping"].module)
    matcher = next(iter(plugin.matcher))()
    runtime = Runtime(PluginStore(tmp_path / "plugins.json"))
    runtime.loaded.add("ping")
    runtime.store.save("ping", PluginSettings(enabled=True, group_ids=["12345"]))
    set_runtime(runtime)
    event = group_event().model_copy(update={"raw_message": "private-content"})
    lines = []
    sink = logger.add(lambda message: lines.append(str(message)), format="{message}")
    try:
        asyncio.run(enforce_plugin_policy(event, matcher))
        asyncio.run(record_plugin_execution(event, matcher, ValueError("private-content")))
    finally:
        logger.remove(sink)
    output = "\n".join(lines)
    assert "plugin=ping" in output and "outcome=error" in output
    assert "ValueError" in output and "elapsed_ms=" in output
    assert "private-content" not in output
