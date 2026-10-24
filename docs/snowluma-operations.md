# SnowLuma 试用运维

本次采用用户确认的独立 Docker/Coolify 试用路线。SnowLuma 承担 QQ 接入，NoneBot 继续负责业务插件、白名单和管理页。先部署到可扫码状态，不自动登录、发消息或切换现有 NoneBot。

## 镜像和持久化

- Compose：`compose.snowluma.yaml`，在现有 QQ Bot 项目的 production 环境建立独立服务。
- 官方镜像：`motricseven7/snowluma:v2.1.1`，linux/amd64 manifest digest `sha256:98f1eba5089b9cbabb350e25dd771f696c9a50f46aeb67399661e76767311eba`。
- VPS 本地标签：`snowluma:trial-v2.1.1-amd64`，`pull_policy: never`。先导入镜像，再由 Coolify 启动；不依赖 VPS 直连 Docker Hub。
- 镜像配置 ID：`sha256:40290fa631cba6374cb14dacc128343199c0503d5fb037ae90f948e2c4556860`。官方 manifest、下载层及解压后的层均已校验 SHA-256；save/load 不保留上游 RepoDigests，使用配置 ID 核对导入结果。
- `/data/qq-bot/snowluma/data`：SnowLuma 配置、数据库及管理凭据。
- `/data/qq-bot/snowluma/qq-config`：QQ 配置。
- `/data/qq-bot/snowluma/qq-data`：QQ 用户数据。

三个目录均独立于 NapCat，不复制或删除 NapCat 登录资料。保留固定 hostname/MAC 和数据目录。日志轮转 10MiB × 3。

官方镜像需要 `SYS_PTRACE` 与 `seccomp=unconfined` 向容器内 QQ 注入 Hook；不使用 privileged、host PID 或 Docker socket，不修改宿主机 ptrace sysctl。原生组件为专有组件，项目采用源码可见非商业许可。资料见 [官方 Docker 文档](https://snowluma.github.io/zh/docs/guide/deploy/docker)及[项目仓库](https://github.com/SnowLuma/SnowLuma)。

## 初始访问和密码

在客户端终端执行：

```bash
ssh -N -L 15099:127.0.0.1:15099 -L 16081:127.0.0.1:16081 ali-root
```

- 管理页：`http://127.0.0.1:15099/`
- 扫码桌面：`http://127.0.0.1:16081/`

两者各有独立密码。首次启动随机生成；凭据仅保存在 VPS 的 root 私有记录中，不进 Git。初始日志可能含密码，不要直接分享完整日志。

在自己的终端，或 Coolify 的 localhost 服务器终端中读取：

```bash
ssh ali-root 'cat /root/qq-bot-snowluma/credentials.json'
```

`webui_username` / `webui_initial_password` 用于管理页，`vnc_password` 用于扫码桌面；文件还保存 OneBot HTTP/WS 的独立令牌。文件权限为 600，不要公开输出。后续在 WebUI 改密后，以新密码为准，这份首次启动记录不会自动同步。

Coolify 服务：[SnowLuma Trial](https://coolify.secret-sealing.club/project/zedd9kjkwxycw6qtsf43f8gv/environment/zi47jjycv0tz997e8bvzzzrg/service/ha3hckthz1jjytu0puicixro)，容器名 `snowluma-ha3hckthz1jjytu0puicixro`。服务器 Compose 副本 `/root/qq-bot-snowluma/compose.yaml`；线上以 Coolify 中的 Compose 为准。

未配置域名时，15099/16081 只绑定 VPS 回环地址；不对公网开放 OneBot 或原生 VNC。若启用 HTTPS 域名，先配置 DNS，再由 Coolify/Traefik 单独路由两个端口。

## 试用和切换

1. 先确认 SnowLuma 管理页和远程桌面可用。health healthy 只代表页面可用，不代表 QQ 已登录或机器人可收发。
2. 同一账号不要同时在 NapCat 与 SnowLuma 登录。用户准备扫码前，先在 Coolify 停止 NapCat，保留其资源和数据。
3. 在远程桌面的真实 QQ 窗口扫码，按手机提示完成验证；不反复自动扫码或重登。
4. 默认 OneBot HTTP/正向 WebSocket 已生成独立 token，启动时已检查两者均非空。登录后核对实际账号配置和正向 WebSocket；现有 NoneBot 使用正向连接，保持这一方向。OneBot 端口仅用于容器内部网络。
5. 切换时，将 NoneBot 接入 SnowLuma 的服务网络，更新 `BOT_ONEBOT_URL` 和 `BOT_ONEBOT_TOKEN`，经 Coolify Restart 应用；记录此前配置供回退。当前阶段不提前执行。
6. 先观察在线持续时间、风险提示和必要插件行为，再决定是否正式替换。社区成功经验不能保证当前账号免风控。

## 重启、备份和回退

在 Coolify 中对 SnowLuma 独立服务执行 Restart；它不重启 NoneBot 或其他业务。镜像升级需要先明确版本、导入对应镜像并更新 Compose，不能直接改用 latest。

备份应在服务停止后归档上述三个目录，并放在 root 私有目录，因其包含 QQ 登录态和密码。不要提交到公开仓库，不要与 NapCat 共用或覆盖卷。

本阶段未切换 NoneBot，停止 SnowLuma 即可结束试用。后续若已切换，先停止 SnowLuma，再恢复 NoneBot 原有网络、URL 和 token，启动 NapCat 并通过 Coolify Restart 更新 NoneBot；必要时由用户重新扫码。不要让两个接入端同时登录同一账号。

## 2026-10-24 部署核验

- 已通过官方 Coolify API 在 QQ Bot / production 创建并启动 SnowLuma Trial。
- Docker 镜像 ID 与上文一致，实际 QQ 包版本 `3.2.32-52194`。
- `docker compose -f compose.snowluma.yaml config --quiet`、`git diff --check` 通过。
- 实际容器 health healthy、RestartCount 0；supervisor 的 QQ 与 SnowLuma 均 RUNNING；日志显示 Hook pipe connected / awaiting login。
- VPS 上管理页 15099、扫码桌面 16081 的 HTTP GET 均返回 200；两端口只绑定 127.0.0.1，3000/3001/5900 未映射宿主机。
- 三个挂载路径、1GiB shm、SYS_PTRACE、seccomp 配置和 node file capability 均核对；无 privileged 或 Docker socket。
- 一次采样约 1GiB 内存，不是长期资源基准。
- NapCat 与 NoneBot 的容器 ID 与准备前一致。本次仅操作新服务；准备期间观测到 Coolify 本体/Redis/DB 的容器 ID 有变化，非本次部署命令触发，未据此宣称所有平台容器保持不变。
- VPS 私有核验记录 `/root/qq-bot-snowluma/verification.json`；启动日志和凭据也只保存在该 root 私有目录。
- 最初导入成功的未使用镜像随后被移除，观测到服务器同时释放约 5GB 空间，疑似平台清理。重新导入后已立即启动服务。未修改全局清理策略或删除其他镜像。
- 两个建议域名尚未解析，当前提供 SSH 转发访问；未添加公网域名路由或修改共享代理。
- 尚未扫码登录、发 QQ 消息、切换 NoneBot、验证长期在线、演练重启/备份恢复；没有运行浏览器自动交互。
