# 插件基础设施与智能左右对称交付

2026-10-24，用户确认后实现并发布。代码提交 `7dd73ae`，镜像权限修复 `786098c`。运行镜像配置 ID：`sha256:da7c89d89ecf826f9a52ced9c088dfb8b36bc9bf3eeb85015d63e16d76cc24bf`。

## 交付内容

- 插件目录自动发现 spec.py；声明与唯一ID执行入口分开，__init__不导入执行模块。开发模板在 examples/plugin_template，无需手工修改 catalog。
- 宿主依据真实 matcher 元数据统一检查群/用户白名单；Depends(plugin_context, use_cache=False) 提供有效 Pydantic 参数及 logger。标准后台任务仍需显式权限检查，未提供第三方代码沙箱。
- 单 JSON 增加稀疏 group_options；群字段同名覆盖公共值，未设置继承，取消勾选恢复继承；列表整体替换。保存时校验完整合并结果，权限不因参数覆盖改变。
- 日志输出到现有 Coolify，包括插件、范围、事件、结果、耗时和异常类型；不新增日志平台或完整聊天归档。
- 智能左右对称支持附图、回复、提示补图，静态PNG和GIF。保留真人优先/动漫后备/无脸中线、左侧裁剪镜像的旧算法。GIF保留时长、循环与透明画布，模型文件保留MIT版权。
- 图片异步限量下载、线程处理；默认60帧/10MiB/单帧400万像素，总解码6400万像素预算。未增加请求队列、恢复状态机或自动重试。
- 管理页旧NapCat链接及提示改为SnowLuma。

## 验证

- 基线 `pytest -q` 16项；实现后 `pytest -q` 27项通过，保留原Starlette/httpx弃用提示。
- `node --check qqbot/static/admin.js`、`node --check qqbot/static/forms.js`、`git diff --check` 通过。
- 测试覆盖群稀疏继承/显式false、0、空列表、null，配置拒绝不改旧文件，真实NoneBot依赖注入与日志内容边界，图像实际像素/GIF时长透明/输入上限和模型加载。
- 一次性OpenCV官方样图检测正向样例：512×512图片检测轴303，输出606×512；测试没有向QQ发送消息。
- 生产镜像内实际导入cv2、加载两个模型并处理PNG通过。无网络隔离容器启动/API验证三个插件均加载且默认关闭。
- 独立代码审阅无阻断问题；NoneBot临时got/reject matcher的_source继承已核对。
- 最初构建因root私有checkout新目录700/文件600，COPY后运行用户无法读取而隔离验证失败。已改COPY --chown=bot:bot并重建、重验，失败镜像未部署。VPS固定Python基础镜像被清理后已从本机补回，未改全局registry或清理策略。
- 正式发布仅通过Coolify重建NoneBot；状态API确认1个连接账号、三个插件已加载，smart_mirror关闭、白名单为空；ping/help原开关和范围保持。plugins.json发布前后逐字节一致，SnowLuma容器ID/启动时间不变，NapCat未运行。
- 未运行浏览器自动交互或截图；尚未由用户在QQ内实际发送图片验证。

## 使用和回退

刷新 https://bot.secret-sealing.club/，找到“智能左右对称”，启用并添加允许群或私聊用户后保存。发送 `/智能左右对称` 附图、回复图片，或按提示补发。无需重新配置旧白名单模块；群参数按需勾选覆盖。

备份：`/root/qq-bot-nonebot/backups/nonebot-20261024T040014Z.tar.gz`。额外私有记录 `plugin-runtime-before.json`、`plugin-runtime-plugins-before.json`、`plugin-runtime-verification.json` 和构建日志位于 `/root/qq-bot-nonebot/`，其中容器快照含凭据，不公开输出。

回退镜像标签 `qqbot:before-plugin-runtime-20261024`。若用户已经保存含group_options或smart_mirror的JSON，旧版无法识别，回退前停止NoneBot并恢复升级前配置备份；不能直接只换旧镜像。SnowLuma及QQ资料不需要恢复。镜像仍可能受平台未使用镜像清理影响，缺失时按旧提交重建。
