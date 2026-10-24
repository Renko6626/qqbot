import asyncio
import base64
from datetime import datetime, timezone
from io import BytesIO

from PIL import Image
from pydantic import ValidationError
import pytest

from qqbot.plugins.scheduled_goodnight.core import GoodnightSender
from qqbot.runtime import Runtime
from qqbot.settings import PluginSettings, PluginStore


class CaptureBot:
    def __init__(self, failing_group=None):
        self.sent = []
        self.failing_group = failing_group

    async def send_group_msg(self, *, group_id, message):
        self.sent.append((group_id, message))
        if group_id == self.failing_group:
            raise RuntimeError("transport failed")


def at(day=25, hour=15, minute=0):
    return datetime(2026, 10, day, hour, minute, tzinfo=timezone.utc)


def test_goodnight_uses_beijing_time_group_overrides_and_daily_attempts(tmp_path):
    runtime = Runtime(PluginStore(tmp_path / "plugins.json"))
    runtime.loaded.add("scheduled_goodnight")
    runtime.store.save("scheduled_goodnight", PluginSettings(
        enabled=True, group_ids=["12345", "67890"], group_user_ids={"12345": []},
        options={"text": "公共晚安"}, group_options={"67890": {"time": "22:00", "text": "早睡"}}))
    encoded = BytesIO()
    Image.new("RGB", (4, 4), "blue").save(encoded, format="PNG")
    runtime.albums.add_image("goodnight", encoded.getvalue(), source="test")
    sender, bot = GoodnightSender(runtime), CaptureBot()

    async def scenario():
        await sender.tick(at(hour=14), bot)
        await sender.tick(at(), None)
        await sender.tick(at(), bot)
        await sender.tick(at(), bot)
        await sender.tick(at(minute=1), bot)
        await sender.tick(at(day=26), bot)

    asyncio.run(scenario())
    assert [group for group, _ in bot.sent] == [67890, 12345, 12345]
    assert [message.extract_plain_text() for _, message in bot.sent] == ["早睡", "公共晚安", "公共晚安"]
    image = bot.sent[1][1][1]
    assert image.type == "image"
    assert base64.b64decode(image.data["file"].removeprefix("base64://")) == encoded.getvalue()


def test_goodnight_reloads_permissions_text_and_album_without_restart(tmp_path):
    runtime = Runtime(PluginStore(tmp_path / "plugins.json"))
    sender, bot = GoodnightSender(runtime), CaptureBot()
    settings = PluginSettings(enabled=True, group_ids=["12345"], options={"text": "初始"})
    runtime.store.save("scheduled_goodnight", settings)

    async def scenario():
        await sender.tick(at(), bot)  # Not actually loaded.
        runtime.loaded.add("scheduled_goodnight")
        settings.enabled = False
        runtime.store.save("scheduled_goodnight", settings)
        await sender.tick(at(), bot)
        settings.enabled = True
        settings.options = {"text": "刚修改的晚安", "album": "empty"}
        runtime.store.save("scheduled_goodnight", settings)
        await sender.tick(at(), bot)
        settings.group_ids = []
        runtime.store.save("scheduled_goodnight", settings)
        await sender.tick(at(day=26), bot)

    asyncio.run(scenario())
    assert [(group, message.extract_plain_text()) for group, message in bot.sent] == [(12345, "刚修改的晚安")]
    assert [segment.type for segment in bot.sent[0][1]] == ["text"]


def test_goodnight_failed_send_does_not_retry_or_block_other_groups(tmp_path):
    runtime = Runtime(PluginStore(tmp_path / "plugins.json"))
    runtime.loaded.add("scheduled_goodnight")
    runtime.store.save("scheduled_goodnight", PluginSettings(enabled=True, group_ids=["12345", "67890"]))
    sender, bot = GoodnightSender(runtime), CaptureBot(failing_group=12345)

    async def scenario():
        await sender.tick(at(), bot)
        await sender.tick(at(), bot)

    asyncio.run(scenario())
    assert [group for group, _ in bot.sent] == [12345, 67890]


def test_goodnight_rejects_invalid_time_before_saving(tmp_path):
    store = PluginStore(tmp_path / "plugins.json")
    with pytest.raises(ValidationError):
        store.save("scheduled_goodnight", PluginSettings(options={"time": "24:00"}))
    assert store.resolve_options("scheduled_goodnight").time == "23:00"
