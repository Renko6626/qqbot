# 公共图集与定时晚安实施计划

**Goal:** 建立多个图集的公共读写能力，接入自动图片监测和定时晚安。
**Architecture:** 宿主 Runtime 提供文件型 AlbumStore，HTTP 路由复用管理认证，两个业务插件仅依赖公共图集。Python 异步循环调度，不增加依赖。
**Spec:** `docs/superpowers/specs/2026-10-25-scheduled-goodnight-design.md`

## 约束

不迁移或删除旧图片、不部署、不增加网页、数据库、自动重试或请求恢复。仅新增核心行为的必要用例，完整改动集中验证。当前工作分支为 `experiment/anime-gate`，在当前目录实施，保留用户未跟踪文件 `milly_cat.jpg`。用户已确认技术路线，直接实施。

## 步骤

- [x] 公共图集：新增 `qqbot/albums.py`、`qqbot/album_api.py`；在 `runtime.py` 提供 `albums`，在 `admin.py` 登记认证后的路由。通过 `tests/test_albums.py` 覆盖真实存储、图集隔离、上传列表查看、鉴权和无效输入。
- [x] 图片监测：Options 新增 `album`；将原 `archive.py` 改为调用公共存储的薄封装，保留业务元数据组装；入口使用宿主实例。适配 `tests/test_plugin_runtime.py` 原有归档验证和配置覆盖验证，移除旧环境变量文档。
- [x] 定时晚安：新增 `qqbot/plugins/scheduled_goodnight/{__init__,spec,core,scheduled_goodnight}.py`。core 中 `GoodnightSender.tick(now, bot)` 使用 Runtime 和真实图集；入口管理启动/关闭循环。`tests/test_goodnight.py` 覆盖北京时间、群覆盖、每日一次、开关和无连接，以及真实图片读取后的发送内容。
- [x] 文档与验证：更新插件开发说明、识别存储文档并写图集接口使用说明；运行 `.venv/bin/pytest -q`、`node --check qqbot/static/admin.js`、`node --check qqbot/static/forms.js`、`git diff --check`，审阅最终差异。

## 审阅关注

图集 ID 不能逃逸存储目录；元数据不包含 URL 或完整消息；监测与 HTTP 使用同一根目录；调度每次读取新配置并遵守群自动事件权限；任务随进程关闭取消。低频使用不额外增加机制。

## 完成记录

- `.venv/bin/pytest -q`：52 passed，2 条依赖弃用警告（Starlette/httpx、NoneBot ForwardRef）。
- `node --check qqbot/static/admin.js`、`node --check qqbot/static/forms.js`：通过。
- `git diff --check`：通过。
- 本地临时运行 NoneBot 的 none driver，加载真实 scheduled_goodnight 插件并执行生命周期启动和关闭，确认任务运行及取消：通过，无真实 QQ 连接。
- 按 requesting-code-review 技能委派一次只读审阅：未发现需要修复的核心问题。
- 没有新增依赖、改动历史图集文件、运行浏览器交互、发送真实 QQ 消息或发布线上。源码未提交，留在当前工作分支。
