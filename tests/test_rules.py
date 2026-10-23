import asyncio

import nonebot
from nonebot.adapters.onebot.v11 import GroupMessageEvent, NoticeEvent
from nonebot.exception import IgnoredException
import pytest

from qqbot.rules import enforce_plugin_policy, event_allowed
from qqbot.runtime import Runtime, set_runtime
from qqbot.settings import PluginSettings, PluginStore


def test_host_gate_checks_real_plugin_without_a_plugin_rule(tmp_path):
    nonebot.init(driver="~none")
    plugin = nonebot.load_plugin("qqbot.plugins.ping")
    matcher = next(iter(plugin.matcher))()
    runtime = Runtime(PluginStore(tmp_path / "plugins.json"))
    runtime.loaded.add("ping")
    runtime.store.save("ping", PluginSettings(enabled=True, group_ids=["12345"],
                                             group_user_ids={"12345": ["11111"]}))
    set_runtime(runtime)
    event = GroupMessageEvent.model_validate({
        "time": 0, "self_id": 10000, "post_type": "message", "message_type": "group",
        "sub_type": "normal", "message_id": 1, "group_id": 12345, "user_id": 22222,
        "anonymous": None, "message": "/测试连接", "raw_message": "/测试连接",
        "font": 0, "sender": {"user_id": 22222, "nickname": "tester"},
    })
    with pytest.raises(IgnoredException):
        asyncio.run(enforce_plugin_policy(event, matcher))
    allowed_event = event.model_copy(update={"user_id": 11111})
    asyncio.run(enforce_plugin_policy(allowed_event, matcher))


def test_unscoped_notice_does_not_inherit_private_access(tmp_path):
    runtime = Runtime(PluginStore(tmp_path / "plugins.json"))
    runtime.loaded.add("ping")
    runtime.store.save("ping", PluginSettings(enabled=True, allow_private=True))
    set_runtime(runtime)
    event = NoticeEvent(time=0, self_id=10000, post_type="notice", notice_type="unknown")
    assert event_allowed("ping", event) is False
