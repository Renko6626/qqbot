# 插件开发约定

当前宿主为一个 NoneBot 容器，QQ 接入由独立 SnowLuma 提供。权限、公共/群参数、表单和执行日志由宿主处理，业务插件只负责自己的功能。

## 从模板创建

复制 `examples/plugin_template/` 到 `qqbot/plugins/<插件ID>/`，把 `plugin_template.py` 重命名为 `<插件ID>.py`，在 `spec.py` 修改 SPEC 的 ID、名称、用途、命令和 Options。

```text
qqbot/plugins/smart_mirror/
  __init__.py      # 不导入处理模块、不注册响应器
  spec.py          # 只声明 SPEC、严格 Pydantic Options，不启动任务或导入重型处理代码
  smart_mirror.py  # NoneBot 命令和处理入口
  core.py          # 可单独验证的业务逻辑（按需）
  models/         # 本插件使用的资源（按需）
```

启动时自动发现这些目录的 `spec.py`，不再修改全局 catalog。只有 `load_on_start=true` 的入口被 NoneBot 加载。入口使用唯一插件 ID 作为文件名，因为 NoneBot 以模块末段识别插件，所有入口都叫 handlers 会冲突。模板不放在 plugins 目录内，不会自动加载。

Options 继承 `qqbot.plugin_api.PluginOptions`，字段提供默认值、中文 title/description 和必要的取值范围。只声明实际需要的配置；密钥仍通过环境变量读取。ID 必须与目录名一致。

## 处理入口

正常注册 NoneBot 命令，宿主依据 matcher 的真实插件及父插件元数据自动检查白名单；补图生成的临时 matcher 也继承归属。无需给每个命令再写白名单装饰器。

```python
from nonebot.params import Depends
from qqbot.context import PluginContext, plugin_context

@matcher.handle()
async def handle(context: PluginContext = Depends(plugin_context, use_cache=False)):
    context.logger.info("准备回复")
    await matcher.finish(context.options.reply_text)
```

`context.options` 是当前插件的实际 Pydantic Options 实例，群参数已经合并，无需手动传插件 ID、群号或拼参数。`use_cache=False` 确保同一事件内不同响应器不共享错误上下文。每次处理读取当前参数，不在模块导入时缓存。

权限检查适用于声明管理的响应器，不是第三方代码沙箱。外部插件须整理为该结构；独立依赖插件的响应器须明确归属，不能假定任意包都自动纳管。定时任务/后台任务不经过消息响应器，执行前仍需显式检查插件开关和目标群范围；关闭开关不会取消已运行任务。

## 群覆盖与参数表单

`options` 为公共参数，`group_options[群号]` 只保存该群勾选覆盖的字段。有效值为公共参数与群字段同名覆盖，未指定继承；列表整体替换，不做递归合并。false、0、空列表和模型允许的 null 都是有效显式覆盖。取消勾选恢复继承，修改公共值后未覆盖字段随之更新；私聊使用公共值。

后端校验完整合并结果，但仅存显式覆盖字段，旧 JSON 不含 group_options 时保留旧行为。不允许给未授权群设置参数；参数不会绕过群或用户白名单。公共值修改导致某群合并结果无效时拒绝保存，并保留旧配置。

同一 schema 自动生成公共和群表单。支持文本、数字、布尔、枚举和基础列表；可空标量支持空值。嵌套、多种非空联合类型和可空列表暂不开放保存。不要手写另一套参数接口/配置表。

## 白名单语义

每个插件有 enabled 和 load_on_start。group_ids 为允许群；group_user_ids 中未设置该群表示全群成员，显式空列表表示无人可用。allow_private=false 关闭私聊；开启后 private_user_ids=null 表示所有用户，列表仅允许指定用户，空列表表示无人。

群消息检查群及发送用户，私聊检查发送用户；notice/request 群自动事件仅按开关和群范围判断。未知/缺少范围事件默认拒绝。自动撤回/禁言等行为仍需另行明确。

新增插件默认 enabled=false、群和私聊均关闭。首次测试由管理员在网页选择范围，不从旧插件自动复制授权。

## 日志和业务数据

统一执行日志输出到 Coolify，包含 plugin、group、user、event、outcome、elapsed_ms 和异常类型。denied 表示权限拒绝，completed 表示本次响应器正常结束（可能只是提示补图），不代表业务动作一定成功。插件通过 context.logger 补充业务结果，不记录完整聊天、下载 URL、图片数据或密钥。错误回复用简短可理解的提示，不把原始网络异常直接发给用户。

数据文件按需放 `/app/data/<插件ID>/`，不得互相导入业务插件。当前没有全量消息归档、网页日志数据库或任务队列；需要数据库/模型/外部接口时先确认范围。

### 公共图集

插件通过 `get_runtime().albums` 读写公共图集，无需调用其他插件。根目录为配置文件同级的 `albums/`，默认 `/app/data/albums/`（容器）或 `data/albums/`（本地）。图集 ID 可在 Options 中使用 `qqbot.albums.AlbumId` 类型，支持现有公共参数及群覆盖。

`add_image(album, data, source=插件ID, metadata=业务信息)` 保留原图并保存 JSON 记录，首次写入自动创建图集；`random_image(album)` 返回随机图片 Path 或 None。这些是同步文件操作，异步处理器使用 `anyio.to_thread.run_sync` 调用。元数据不放完整消息、下载 URL 或密钥。完整接口与示例见[图集与定时晚安](albums-goodnight.md)。图集模块不会执行插件权限判断，消息和后台发送仍分别遵守宿主权限检查。

## 智能左右对称

命令 `/智能左右对称`，支持同条附图、回复图片或按提示补发。先尝试真人、再动漫人脸，取最大人脸中心；无脸用中线，左侧镜像到右侧。保留旧算法的裁剪语义，输出宽度可能变化；GIF 每帧处理后统一透明画布，保留时长和循环设置。

默认最多60帧、10MiB、单帧400万像素，另有总解码6400万像素上限；过大输入提示缩小或减帧，不加入排队/自动重试。计算在线程中执行。动漫 XML 内保留原 MIT 许可，仅迁移这一操作，没有复制旧图片数据或其他图像功能。

## 开发与发布

本地 `uv sync`，前端使用 Node 22.22.1（最低 22.12）并运行 `npm ci --prefix web`、`npm run build --prefix web`；设置 `.env` 后执行 `uv run --env-file .env python -m qqbot.app`。不需要 QQ 时留空 BOT_ONEBOT_URL。管理页默认8080；本地默认禁用网页进程重启，Docker中由unless-stopped拉起。

Vue 3 + TypeScript 源码位于 `web/src/`，`components/` 按插件编辑、群规则、schema 参数、权限预览和图集拆分；`schema.ts` 负责值转换和白名单配置序列化，`api.ts` 复用现有 API 和认证。插件 schema 继续由后端提供，不为新插件手写一套参数表单。群覆盖只提交显式字段，草稿保留在已挂载组件中，不增加持久化草稿。前端不使用 Router、Pinia 或 UI 库。

Vite 输出到 `qqbot/static/`，该目录由构建生成并 Git 忽略。修改前端后需重新构建，本地也可用 `npm run dev --prefix web` 启动 Vite（API 代理到 127.0.0.1:8080，仍需先通过后端登录）；生产不运行 Vite 开发服务。Docker 的 Node 阶段完成构建后将静态文件复制进原 Python 镜像，不增加运行服务和端口。

新增依赖后运行 `uv lock`、`uv export --no-dev --format requirements-txt --output-file requirements.lock`，再重建镜像。仅网页进程重启不能获得新源码或依赖；新增插件按现有SSH pull/build和Coolify Restart发布，不在运行容器pip安装，不热卸载。

验证用 `uv run pytest -q`、`npm test --prefix web`（Node 自带测试工具）和 `npm run build --prefix web`（包含 Vue/TypeScript 类型检查）。页面默认仅截图，不自动点击填表或发QQ消息。TypeScript 固定为与当前 vue-tsc 兼容的 5.9.3，不盲目升级到 7.x；依赖变更须更新 `web/package-lock.json`。
