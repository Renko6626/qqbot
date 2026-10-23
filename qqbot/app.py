import os
from pathlib import Path

import nonebot
from nonebot.adapters.onebot.v11 import Adapter

from .admin import register_admin
from .catalog import CATALOG
from .runtime import Runtime, set_runtime
from .settings import PluginStore


def main():
    username = os.environ.get("BOT_ADMIN_USER", "")
    password = os.environ.get("BOT_ADMIN_PASSWORD", "")
    if not username or not password:
        raise ValueError("必须设置 BOT_ADMIN_USER 和 BOT_ADMIN_PASSWORD")
    url = os.environ.get("BOT_ONEBOT_URL", "")
    token = os.environ.get("BOT_ONEBOT_TOKEN", "")
    if url and not token:
        raise ValueError("连接 NapCat 时必须设置 BOT_ONEBOT_TOKEN")
    nonebot.init(
        driver="~fastapi+~websockets", host="0.0.0.0",
        port=int(os.environ.get("PORT", "8080")), log_level="INFO",
        onebot_ws_urls=[url] if url else [], onebot_access_token=token,
        command_start={"/"}, command_sep={"."},
    )
    runtime = Runtime(PluginStore(Path(os.environ.get("BOT_CONFIG_PATH", "data/plugins.json"))))
    set_runtime(runtime)
    driver = nonebot.get_driver()
    driver.register_adapter(Adapter)
    for plugin_id, spec in CATALOG.items():
        if not runtime.store.get(plugin_id).load_on_start:
            continue
        plugin = nonebot.load_plugin(spec.module)
        if plugin is None:
            runtime.load_errors[plugin_id] = "加载失败，请在 Coolify 查看启动日志"
        else:
            runtime.loaded.add(plugin_id)
    register_admin(driver.server_app, runtime, username, password,
                   os.environ.get("BOT_COOLIFY_URL", ""))
    nonebot.run()


if __name__ == "__main__":
    main()
