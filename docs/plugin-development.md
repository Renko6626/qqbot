# 插件开发约定

启动：`uv sync`，设置 `.env` 后 `uv run --env-file .env python -m qqbot.app`。本地无需连接QQ时，不设置 BOT_ONEBOT_URL。管理页监听 PORT（默认8080），账号密码必须设置。

## 增加功能

1. 在 `qqbot/plugins/` 新增模块。模块只负责自己的消息入口与功能，不导入其他业务插件。
2. 在 `qqbot/catalog.py` 添加 PluginSpec，声明稳定ID、名称、用途、命令和参数模型。没有额外参数时使用 NoOptions；目前界面支持简单文本参数，复杂配置随具体需求设计。
3. 每个消息入口都挂 `rule=permitted("插件ID")`。它统一检查实际加载、全局开关和当前群/私聊范围。后台任务如需遵守开关，也应在执行前检查配置。
4. 处理时通过 `get_runtime().store.get("插件ID").options` 读取当前参数，不在导入时缓存配置。
5. 在管理页配置功能范围。默认不响应任何会话；设置允许的群或私聊并开启功能后才使用。

保存会替换这个插件的完整配置，不合并旧字段。当前单进程、单管理员低频使用，不提供多管理员冲突合并。外部修改JSON后需重启，进程内配置以管理页保存的值为准。

## 加载与启用

启用是处理消息的开关，保存后作用于后续事件；已执行中的处理不会取消。启动时加载决定下次进程是否导入模块。修改后去Coolify重启；管理页展示实际加载结果和是否存在待重启变更。配置错误会阻止进程启动；在Coolify日志中检查并修正JSON，不会静默重置配置。

不自动扫描旧插件目录，不支持热卸载，不在运行容器中安装第三方包。新增依赖先更新pyproject.toml、运行 `uv lock`，再执行 `uv export --no-dev --format requirements-txt --output-file requirements.lock > /dev/null` 并重建镜像。

## 数据与秘密

`data/plugins.json` 只保存插件配置，不存密码、OneBot令牌或模型密钥。秘密由环境变量提供，不通过管理API返回。插件业务文件放在独立的 `data/<插件ID>/`；需要数据库、模型或新增外部接口时，先确认必要性和迁移范围。

## 验证

`uv run pytest -q` 验证配置、权限和管理API；`node --check qqbot/static/admin.js` 检查脚本语法。页面默认仅截图查看。接入生产前默认关闭功能，由用户选择群并实际使用；不要自动发送QQ消息、撤回或禁言。
