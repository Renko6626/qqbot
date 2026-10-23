import pytest
from pydantic import ValidationError

from qqbot.settings import PluginSettings, PluginStore
from qqbot.runtime import Runtime


def test_plugin_gate_uses_enabled_scope_and_actual_loaded_state(tmp_path):
    store = PluginStore(tmp_path / "plugins.json")
    runtime = Runtime(store)
    runtime.loaded.add("ping")
    assert not runtime.allowed("ping", "12345")
    store.save("ping", PluginSettings(enabled=True, group_ids=["12345"]))
    assert runtime.allowed("ping", "12345")
    assert not runtime.allowed("ping", "67890")
    assert not runtime.allowed("ping", None)
    assert not runtime.allowed("help", "12345")


def test_saved_options_and_private_scope_survive_restart(tmp_path):
    path = tmp_path / "plugins.json"
    store = PluginStore(path)
    store.save("ping", PluginSettings(enabled=True, allow_private=True,
                                     options={"reply_text": "机器人已连接"}))
    restored = PluginStore(path)
    runtime = Runtime(restored)
    runtime.loaded.add("ping")
    assert runtime.allowed("ping", None)
    assert restored.get("ping").options == {"reply_text": "机器人已连接"}


def test_loading_change_takes_effect_on_next_process(tmp_path):
    store = PluginStore(tmp_path / "plugins.json")
    runtime = Runtime(store)
    runtime.loaded.add("ping")
    store.save("ping", PluginSettings(load_on_start=False, enabled=True,
                                     group_ids=["12345"]))
    assert runtime.allowed("ping", "12345")
    assert runtime.plugin_status("ping")["restart_required"] is True
    after_restart = Runtime(PluginStore(store.path))
    assert not after_restart.allowed("ping", "12345")


def test_invalid_options_leave_saved_config_unchanged(tmp_path):
    store = PluginStore(tmp_path / "plugins.json")
    store.save("ping", PluginSettings(options={"reply_text": "hello"}))
    with pytest.raises(ValidationError):
        store.save("ping", PluginSettings(options={"reply_text": ""}))
    assert PluginStore(store.path).get("ping").options["reply_text"] == "hello"
