import pytest
from typing import Literal
from pydantic import ValidationError

from qqbot.settings import PluginSettings, PluginStore
from qqbot.runtime import Runtime
from qqbot.catalog import CATALOG, NoOptions, PluginSpec


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


def test_group_member_and_private_whitelists_are_independent(tmp_path):
    runtime = Runtime(PluginStore(tmp_path / "plugins.json"))
    runtime.loaded.add("ping")
    runtime.store.save("ping", PluginSettings(
        enabled=True, group_ids=["12345", "67890"],
        group_user_ids={"12345": ["11111"]},
        allow_private=True, private_user_ids=["22222"],
    ))
    assert runtime.allowed("ping", "12345", "11111")
    assert not runtime.allowed("ping", "12345", "22222")
    assert runtime.allowed("ping", "67890", "22222")
    assert runtime.allowed("ping", None, "22222")
    assert not runtime.allowed("ping", None, "11111")
    assert not runtime.allowed("ping", "99999", "22222")


def test_legacy_file_keeps_full_group_and_private_access(tmp_path):
    path = tmp_path / "plugins.json"
    path.write_text('{"plugins":{"ping":{"enabled":true,"group_ids":["12345"],"allow_private":true}}}')
    runtime = Runtime(PluginStore(path))
    runtime.loaded.add("ping")
    assert runtime.allowed("ping", "12345", "11111")
    assert runtime.allowed("ping", None, "22222")


def test_empty_member_whitelist_denies_every_member(tmp_path):
    runtime = Runtime(PluginStore(tmp_path / "plugins.json"))
    runtime.loaded.add("ping")
    runtime.store.save("ping", PluginSettings(enabled=True, group_ids=["12345"],
                                             group_user_ids={"12345": []},
                                             allow_private=True, private_user_ids=[]))
    assert not runtime.allowed("ping", "12345", "11111")
    assert not runtime.allowed("ping", None, "11111")


def test_loading_failure_is_distinct_from_pending_configuration(tmp_path):
    runtime = Runtime(PluginStore(tmp_path / "plugins.json"))
    runtime.load_errors["ping"] = "加载失败"
    status = runtime.plugin_status("ping")
    assert status["load_state"] == "failed"
    assert status["restart_required"] is False


def test_typed_plugin_options_keep_json_types(monkeypatch, tmp_path):
    class Options(NoOptions):
        enabled: bool = False
        count: int = 1
        ratio: float = 0.5
        mode: Literal["brief", "full"] = "brief"
        labels: list[str] = []

    monkeypatch.setitem(CATALOG, "sample", PluginSpec("sample", "Sample", "", (), Options))
    store = PluginStore(tmp_path / "plugins.json")
    store.save("sample", PluginSettings(options={"enabled": True, "count": 3, "ratio": 0.25,
                                               "mode": "full", "labels": ["001", "two"]}))
    assert PluginStore(store.path).get("sample").options == {
        "enabled": True, "count": 3, "ratio": 0.25, "mode": "full", "labels": ["001", "two"]}
    with pytest.raises(ValidationError):
        store.save("sample", PluginSettings(options={"enabled": "false"}))
