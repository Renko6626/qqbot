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


@pytest.fixture
def rating_plugins(monkeypatch, tmp_path):
    from io import BytesIO
    from pathlib import Path
    from types import SimpleNamespace
    import httpx
    from PIL import Image
    from nonebot.rule import TrieRule
    from qqbot.image_rating import service

    pytest.importorskip("onnxruntime")
    nonebot.init(driver="~none")
    plugins = {key: nonebot.get_plugin(key) or nonebot.load_plugin(CATALOG[key].module)
               for key in ["anime_rating", "anime_rating_watch"]}
    runtime = Runtime(PluginStore(tmp_path / "plugins.json"))
    runtime.loaded.update(plugins)
    set_runtime(runtime)
    monkeypatch.setenv("BOT_DEEPGHS_MODEL_PATH", str(
        Path(__file__).parent / "fixtures" / "rating_channel_means.onnx"))
    service.get_engine.cache_clear()
    requests, sent, payloads = [], [], {}
    for color in ["red", "blue", "lime"]:
        buffer = BytesIO(); Image.new("RGB", (16, 16), color).save(buffer, format="PNG")
        payloads[color] = buffer.getvalue()

    def respond(request):
        requests.append(str(request.url))
        return httpx.Response(200, content=payloads[request.url.path.lstrip("/")])

    client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client(
        transport=httpx.MockTransport(respond), **kwargs))
    root = tmp_path / "archive"
    monkeypatch.setenv("BOT_DEEPGHS_ARCHIVE_DIR", str(root))

    class CaptureBot(Bot):
        async def send(self, event, message, **kwargs):
            sent.append(message)
            return {"message_id": 1}

    bot = CaptureBot(Adapter(nonebot.get_driver()), "10000")

    def run(plugin_id, event):
        matcher = next(iter(plugins[plugin_id].matcher))()
        asyncio.run(enforce_plugin_policy(event, matcher))
        state = {}
        TrieRule.get_value(bot, event, state)
        asyncio.run(matcher.run(bot, event, state))

    yield SimpleNamespace(runtime=runtime, run=run, sent=sent, requests=requests,
                          root=root, payloads=payloads)
    service.get_engine.cache_clear()


@pytest.mark.parametrize("colors,reply,saved_count,reply_count", [
    (["red"], "命中提示", 0, 0),
    (["blue"], "", 1, 0),
    (["red", "blue", "lime"], None, 2, 1),
])
def test_monitor_saves_only_hits_and_replies_once(rating_plugins, colors, reply, saved_count, reply_count):
    import json
    from nonebot.adapters.onebot.v11 import Message, MessageSegment

    harness = rating_plugins
    harness.runtime.store.save("anime_rating_watch", PluginSettings(
        enabled=True, group_ids=["12345"], options={} if reply is None else {"reply_text": reply}))
    images = [MessageSegment("image", {"file": "test", "url": f"https://images.example/{color}"})
              for color in colors]
    event = group_event().model_copy(update={"message": Message(images)})
    harness.run("anime_rating_watch", event)
    records = list(harness.root.rglob("*.json"))
    assert len(records) == saved_count and len(harness.sent) == reply_count
    originals = []
    for path in records:
        record = json.loads(path.read_text())
        assert record["group_id"] == "12345" and record["message_id"] == "1"
        assert record["scores"]["r15"] + record["scores"]["r18"] >= 0.8
        originals.append(path.with_name(record["image_file"]).read_bytes())
    assert sorted(originals) == sorted(harness.payloads[c] for c in colors if c != "red")
    if reply_count:
        import base64
        from io import BytesIO
        from PIL import Image

        assert harness.sent[0][0] == MessageSegment.reply(1)
        assert harness.sent[0].extract_plain_text() == ("我吃！" if reply is None else reply)
        assert [segment.type for segment in harness.sent[0]] == ["reply", "text", "image"]
        file = harness.sent[0][2].data["file"]
        assert file.startswith("base64://")
        with Image.open(BytesIO(base64.b64decode(file.removeprefix("base64://")))) as image:
            assert image.format == "JPEG"
            image.verify()


def test_monitor_has_independent_permissions_and_group_overrides(rating_plugins):
    from nonebot.adapters.onebot.v11 import Message, MessageSegment
    from nonebot.exception import IgnoredException

    harness = rating_plugins
    settings = PluginSettings(enabled=True, group_ids=["12345"],
                              group_options={"12345": {"threshold": 0.95}})
    harness.runtime.store.save("anime_rating_watch", settings)
    assert not harness.runtime.allowed("anime_rating", "12345", "11111")
    event = group_event().model_copy(update={"message": Message(
        MessageSegment("image", {"file": "test", "url": "https://images.example/blue"}))})
    harness.run("anime_rating_watch", event)
    assert not list(harness.root.rglob("*.json"))  # Group threshold overrides public 0.8.
    settings.group_options = {"12345": {"max_pixels": 1}}
    harness.runtime.store.save("anime_rating_watch", settings)
    harness.run("anime_rating_watch", event)
    assert not list(harness.root.rglob("*.json")) and not harness.sent
    settings.enabled = False
    harness.runtime.store.save("anime_rating_watch", settings)
    harness.runtime.store.save("anime_rating", PluginSettings(enabled=True, group_ids=["12345"]))
    assert harness.runtime.allowed("anime_rating", "12345", "11111")
    before = len(harness.requests)
    with pytest.raises(IgnoredException):
        harness.run("anime_rating_watch", event)
    assert len(harness.requests) == before


def test_manual_command_uses_shared_analysis_and_is_excluded_from_monitor(rating_plugins):
    from nonebot.adapters.onebot.v11 import Message, MessageSegment
    from qqbot.plugins.anime_rating_watch.anime_rating_watch import is_monitor_message

    harness = rating_plugins
    harness.runtime.store.save("anime_rating", PluginSettings(enabled=True, group_ids=["12345"]))
    message = Message("/色图识别 ") + MessageSegment("image", {
        "file": "test", "url": "https://images.example/blue"})
    event = group_event().model_copy(update={"message": message, "raw_message": str(message)})
    assert not is_monitor_message(event)
    harness.run("anime_rating", event)
    assert len(harness.requests) == 1
    assert len(harness.sent) == 1 and "DeepGHS" in str(harness.sent[0])
    assert not harness.root.exists()


def test_monitor_does_not_reply_when_archive_cannot_be_written(rating_plugins):
    from nonebot.adapters.onebot.v11 import Message, MessageSegment

    harness = rating_plugins
    harness.root.write_text("occupied")
    harness.runtime.store.save("anime_rating_watch", PluginSettings(
        enabled=True, group_ids=["12345"], options={"reply_text": "命中提示"}))
    event = group_event().model_copy(update={"message": Message(MessageSegment("image", {
        "file": "test", "url": "https://images.example/blue"}))})
    harness.run("anime_rating_watch", event)
    assert harness.root.read_text() == "occupied" and not harness.sent
