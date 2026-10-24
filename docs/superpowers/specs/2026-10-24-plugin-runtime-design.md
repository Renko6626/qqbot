# 插件基础设施与智能左右对称

用户已确认：单 NoneBot、现有 FastAPI/原生前端、单 plugins.json；增加可选群参数覆盖、插件日志、开发模板和自动声明发现，迁移智能左右对称，保留静态图/GIF/人脸检测；允许 Pillow/NumPy/opencv-python-headless。

采用本仓库插件目录的 spec.py 声明 + <插件ID>.py 执行模块，__init__.py 不注册响应器。替代继续手工维护全局 catalog；不扫描任意第三方包、不热卸载。声明含 PluginSpec 和严格 Pydantic Options，启动发现生成 catalog，只有选中 load_on_start 的 handlers 被导入。

宿主根据真实 NoneBot matcher 的插件元数据统一执行白名单检查，Depends(plugin_context) 提供解析后的 options 与插件 logger；模板和内置插件均使用这一入口。后台任务依旧需要显式检查，不建立调度系统。

PluginSettings 增加 group_options: dict[群号, dict]，只允许已授权群。有效参数为公共 options 覆盖同名群字段；列表整体替换，未指定继承，null 只在参数模型允许时合法。后端合并校验，保存仅显式覆盖字段，旧 JSON 默认无覆盖。

前端各群提供同一 schema 生成的可选覆盖字段，显示继承/覆盖，删除覆盖恢复公共值；不改变其他群/私聊授权。日志沿用现有 stdout/Coolify，记录插件、范围、结果、耗时和异常类型，不记录图片/URL/密钥，不加队列、日志数据库或新接口。

智能左右对称独立插件 smart_mirror：/智能左右对称，附图/回复图/提示后补图，真人与动漫级联最大人脸轴，没脸用中线，左侧镜像；GIF 保留时长、统一帧画布，沿用60帧限制。异步下载、线程内处理，简单文件大小/像素限制与错误提示，不搭并发恢复机制。默认功能关闭，不迁移其他图像功能、旧AI或旧数据。
