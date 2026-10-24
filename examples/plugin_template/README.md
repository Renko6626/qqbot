# 本仓库插件模板

复制此目录到 `qqbot/plugins/<插件ID>/`，将 `plugin_template.py` 改名为 `<插件ID>.py`，并修改 spec.py 的 SPEC ID、名称、命令、Options。保持 __init__.py 不导入执行入口。

不再编辑 catalog、不复制白名单代码或管理表单。按模板的 Depends(plugin_context, use_cache=False) 读取有效参数和插件 logger。新插件默认关闭；重建发布后在管理页选择群/用户范围。

详见 [开发约定](../../docs/plugin-development.md)。
