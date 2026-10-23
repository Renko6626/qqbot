from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from qqbot.admin import register_admin
from qqbot.runtime import Runtime
from qqbot.settings import PluginStore


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
