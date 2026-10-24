# Plugin runtime implementation plan

**Goal:** 自动发现插件声明，统一授权/群参数/日志，并迁移智能左右对称。
**Architecture:** spec.py 静态声明、<插件ID>.py 按选择加载；现有 JSON 增加群覆盖；Depends 注入上下文；现有原生表单延展。
**Tech Stack:** NoneBot/FastAPI/Pydantic，原生JS，Pillow/NumPy/OpenCV headless/httpx。
**Spec:** docs/superpowers/specs/2026-10-24-plugin-runtime-design.md

## Global constraints
- 不引入数据库/服务/队列；不改SnowLuma、不自动发送QQ消息。
- 新插件默认关闭；保留现有ping/help授权与公共参数。
- 页面只截图检查，不自动点击或填写；测试聚焦配置覆盖/权限/真实图像处理。

## Tasks / ownership
- [x] Root: qqbot/plugin_api.py 声明PluginSpec/PluginOptions（旧NoOptions别名）；catalog.py发现 qqbot/plugins/*/spec.py 的 SPEC，module指向各自唯一插件ID入口。迁移ping/help到包，__init__为空。
- [x] Root: settings.py增加group_options并合并验证；runtime.py/新context.py提供有效Options；rules.py统一matcher归属、授权、结果/耗时日志。旧测试按实际新模块路径更新，增加覆盖继承与真实插件依赖测试。
- [x] Frontend worker: 仅static/{forms.js,admin.js,index.html,admin.css}，群行可编辑可选覆盖；settings.group_options字段；同schema生成表单，不改变其他配置。同步链接SnowLuma。JS语法检查。
- [x] Image worker: 仅qqbot/plugins/smart_mirror/**、tests/test_smart_mirror.py。spec.SPEC=PluginSpec('smart_mirror',...,Options)；处理器Depends(plugin_context)取得PluginContext(options Pydantic实例、logger)。保留动漫XML版权；不改依赖文件。
- [x] Root: pyproject/锁文件增加批准依赖，examples/plugin_template模板和开发文档。集中pytest、JS语法、构建/隔离启动，独立审阅。
- [ ] Root: 备份NoneBot配置，发布已验证镜像到Coolify，核对QQ连接/原配置/新插件关闭；更新文档与交付记录。

## Review focus
- 群覆盖不能绕过群/成员白名单，不能把默认值误存为覆盖。
- 未选择加载的执行入口不能因发现声明被导入；新插件不能意外启用。
- 临时got响应器继续受统一授权，取补图时有效配置。
- GIF透明与时长、无脸回退，损坏/过大输入明确报错。
- 配置旧文件兼容、保持当前账号连接，不因发布重启SnowLuma。

验证记录：基线16项通过；实现后27项通过（保留既有Starlette弃用提示）；JS语法通过；独立审阅无阻断问题。一次真实OpenCV样图检测轴303、输出606×512，符合左侧裁剪镜像。入口统一改为唯一ID文件名，避免NoneBot模块末段ID冲突。
