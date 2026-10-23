from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from qqbot.admin import register_admin
from qqbot.runtime import Runtime
from qqbot.settings import PluginSettings, PluginStore


@pytest.fixture
def client(tmp_path):
    app = FastAPI()
    runtime = Runtime(PluginStore(tmp_path / "plugins.json"))
    runtime.loaded.update({"ping", "help"})
    register_admin(app, runtime, "operator", "test-password", "https://coolify.example/")
    with TestClient(app) as client:
        yield client, runtime


def test_admin_data_requires_credentials(client):
    http, _ = client
    assert http.get("/api/plugins").status_code == 401
    assert http.get("/").status_code == 401
    assert http.get("/api/plugins", auth=("operator", "wrong")).status_code == 401


def test_admin_save_changes_real_plugin_gate(client):
    http, runtime = client
    payload = {"enabled": True, "group_ids": ["12345"],
               "options": {"reply_text": "已连接"}}
    response = http.put("/api/plugins/ping", json=payload,
                        auth=("operator", "test-password"),
                        headers={"X-Requested-With": "qqbot-admin"})
    assert response.status_code == 200
    assert runtime.allowed("ping", "12345")
    assert not runtime.allowed("ping", "67890")
    assert response.json()["settings"]["options"]["reply_text"] == "已连接"


def test_invalid_or_cross_site_write_is_rejected(client):
    http, runtime = client
    auth = ("operator", "test-password")
    assert http.put("/api/plugins/ping", auth=auth, json={"enabled": True}).status_code == 403
    headers = {"X-Requested-With": "qqbot-admin"}
    assert http.put("/api/plugins/ping", auth=auth, headers=headers,
                    json={"group_ids": ["not-a-group"]}).status_code == 422
    assert http.put("/api/plugins/ping", auth=auth, headers=headers,
                    json={"options": {"unknown": "value"}}).status_code == 422
    assert not runtime.allowed("ping", "12345")


def test_permission_preview_uses_the_saved_rules(client):
    http, runtime = client
    runtime.store.save("ping", PluginSettings(
        enabled=True, group_ids=["12345"], group_user_ids={"12345": ["11111"]}))
    response = http.get("/api/plugins/ping/permission", params={"group_id": "12345", "user_id": "22222"},
                        auth=("operator", "test-password"))
    assert response.status_code == 200
    assert response.json() == {"allowed": False, "reason": "该用户不在此群的插件白名单中"}


def test_process_restart_requires_login_and_same_origin_header(client):
    http, _ = client
    assert http.post("/api/restart").status_code == 401
    assert http.post("/api/restart", auth=("operator", "test-password")).status_code == 403
