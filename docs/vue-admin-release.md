# Vue 管理页、公共图集与定时晚安发布记录

2026-10-25，用户明确要求实装后发布。代码提交 `030ba31be5b26ca560f11ba43097d6ae9b989a4e` 已推送 `main` 与 `experiment/anime-gate`，服务器 `/opt/qqbot` 的 main 已快进到该提交。

## 发布内容

- Vue 3 + Vite + TypeScript 管理页，桌面双列表单、手机插件选择器、紧凑顶栏和图集工具栏。
- 公共多图集读写、认证后管理页查看/上传/删除图片和空图集；自动图片监测改写公共图集。旧图片未迁移或删除。
- 定时晚安插件已加载，默认关闭、群范围为空，由用户配置时间、群、文案和图集后启用。
- 本分支原有二维识别闸门一同发布，补齐固定校验模型。识别规则和局限见图片识别说明；真实群效果仍待使用反馈。

## 构建与切换

沿用既有 SSH 构建和 Coolify 管理方式，没有新服务、端口、代理配置或运行环境变量改动。

- 构建镜像 `qqbot:git-030ba31be5b26ca560f11ba43097d6ae9b989a4e`，镜像 ID `sha256:93a8c087e5cf76c9e0e207421473305f92803e57399bb132be8fa9e3f723ec16`，`qqbot:manual` 同指向。
- 首次导入 `node:22.22.1-bookworm-slim`，官方来源 digest `sha256:4f77a690f2f8946ab16fe1e791a3ac0667ae1c3575c3e4d0d4589e9ed5bfaf3d`。Node 只用于 Docker 构建阶段，运行镜像内无 Node。
- gate 权重放在现有数据卷 `models/deepghs_gate/model.onnx`，SHA-256 `ea8f4497b0e3ee86f43b6a6fd38884e25f960979a1debb5c4e1ee6a22e80d111`，容器 UID1000 可读。
- 镜像内 Vue 类型检查和生产构建成功；运行用户 UID1000、首页及两个生成资产的读取、现有配置解析通过。
- 本会话 Coolify MCP token 不可用，使用已授权 SSH 在 Coolify 容器内调用平台原有 `RestartService` 动作，仅针对 NoneBot 服务 `8hzqwaltqvmjo73d5lkv2rll`，`pullLatestImages=false`，activity ID `18`；没有手动 docker compose up 或重启共享代理。

## 上线检查

- NoneBot 容器 healthy，运行 revision 与上述提交一致，6 个插件加载，无加载错误。
- 回环与公网 `https://bot.secret-sealing.club` 的 healthz 正常；认证后的首页、JS、CSS、插件列表和图集列表均 HTTP200。页面及资产字节与运行镜像一致。
- 匿名首页、图集接口及资产返回401。没有执行浏览器自动点击、填表、上传、删除或真实 QQ 发消息。
- 插件配置文件 SHA-256 与发布前一致；SnowLuma、Traefik 容器 ID 未变。
- **QQ 连接数为0**：NoneBot 可解析协议端地址，但连接 3001 被拒绝；SnowLuma 的监听列表不含3001，其日志提示等待登录。QQ 和 SnowLuma 进程仍为 RUNNING。没有擅自重启 SnowLuma或处理用户登录；用户需到 SnowLuma 完成 QQ 登录，NoneBot 持续按原逻辑重连。

## 备份与回退

- 配置/数据备份：`/root/qq-bot-nonebot/backups/nonebot-20261024T201955Z.tar.gz`。
- 旧镜像保留为 `qqbot:before-vue-20261025`，原运行提交为 `1529291628899e55f386cdfe7a66f14b9d8510f6`。
- 发布前快照、镜像构建日志及只读核验记录：`/root/qq-bot-nonebot/release-vue-20261025-030ba31/`。记录不含明文凭据。
- 必要时通过既有 `ops/nonebot.sh promote` 选择旧镜像，再使用 Coolify Restart。若后续用户保存了新插件配置，旧宿主无法识别新插件 ID，回退前须停机并恢复升级前配置备份；不应将旧配置直接覆盖正在写入的服务。
