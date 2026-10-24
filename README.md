# QQ Bot 运维

Coolify 项目：QQ Bot。当前由 SnowLuma 提供 QQ 接入，NoneBot 负责插件；两个资源分别启停、发布和查看日志。NapCat 已停用，保留资源和数据供回退。

SnowLuma 独立试用基础设施见 [SnowLuma 运维](docs/snowluma-operations.md)。管理页 https://snowluma.secret-sealing.club/，扫码桌面 https://qq-desktop.secret-sealing.club/。其数据与 NapCat 分开保存，NoneBot 默认通过内部正向 WebSocket 连接 SnowLuma。

## NoneBot 插件管理

管理页：https://bot.secret-sealing.club/ 。登录账号密码位于本地 `.env`（Git忽略），打开页面时在浏览器认证框中输入。与NapCat令牌、Coolify账号分别管理。

已接入连接检查与帮助，默认功能关闭。每个群可选择全群成员或指定成员，私聊可关闭、允许全部用户或指定用户；保存后可以使用 `/测试连接` 和 `/帮助`。权限预览按已保存配置显示允许/拒绝原因，“按群查看”汇总各插件范围。参数表单支持文本、数字、布尔、枚举和简单列表。群参数可逐项勾选覆盖公共值，未覆盖的字段持续继承公共值。

已新增“智能左右对称”，默认关闭。在管理页启用并添加允许的群后，可发送 `/智能左右对称` 附图、回复图片，或按提示补发图片；支持静态图和 GIF。新插件从声明自动发现，开发模板见 `examples/plugin_template/`。插件执行日志在 Coolify 查看。

已部署独立管理的“手动图片识别”和“自动图片监测”，共用ORT CPU引擎。自动功能仅在`r15+r18≥0.8`时归档，默认引用原消息回复“我吃！”和猫猫表情包，回复文案留空时只保存。安装、群参数及归档目录见[图片识别说明](docs/deepghs-prototype.md)，新插件默认关闭，需分别启用并添加群白名单；[发布及回退记录](docs/deepghs-deployment.md)。

“启动时加载”改变后，可以直接点击管理页的 **重启 NoneBot 进程**。页面区分已加载、未加载、加载失败和待重启变更。进程重启会短暂断开连接，再由Docker自动拉起；环境变量和镜像更新仍需到Coolify点Restart。没有增加管理服务、平台token或Docker socket权限。

- [功能容器运维](docs/nonebot-operations.md)
- [插件开发约定](docs/plugin-development.md)
- [旧插件迁移清单](docs/legacy-inventory.md)
- [本次交付核验](docs/nonebot-delivery.md)

源码仓库：<https://github.com/Renko6626/qqbot>（公开）。服务器源码位于 `/opt/qqbot`。更新时 SSH 执行 `cd /opt/qqbot && bash ops/nonebot.sh update`，构建成功后在 Coolify 的 NoneBot 资源点 **Restart**；详见功能容器运维手册。不会自动发布，也不会重启 NapCat。

现阶段不整包复制旧 `/root/mybot`。AI对话、RAG、图片模型及旧业务插件均待按实际需要逐个整理。代码依赖通过 `uv.lock` 和 `requirements.lock` 固定；本机检查使用 `uv run pytest -q`。

- 项目：https://coolify.secret-sealing.club/project/zedd9kjkwxycw6qtsf43f8gv
- 环境：production（zi47jjycv0tz997e8bvzzzrg）
- NapCat：https://coolify.secret-sealing.club/project/zedd9kjkwxycw6qtsf43f8gv/environment/zi47jjycv0tz997e8bvzzzrg/service/n4wkgdcd9fmbitucekxzuyk5
- 服务器：ali-root（47.94.44.152）

## NapCat 回退资源（当前停用）

以下是旧 NapCat 的维护记录。只有明确回退时才启动，避免与 SnowLuma 同时登录同一账号。

直接打开 https://napcat.secret-sealing.club/webui/ ，输入原有 WebUI 令牌并扫码登录 QQ，无需 SSH 隧道。

令牌也可以在 Coolify 的服务器 localhost 网页终端中执行 `cat /root/qq-bot-napcat/credentials.json` 查看，使用其中的 webui_token。不要将输出公开分享。

SSH 隧道保留为备用访问方式，在自己电脑的终端建立转发并保持连接：

```bash
ssh -N -L 6099:127.0.0.1:6099 ali-root
```

打开 http://127.0.0.1:6099/webui/ 。如果电脑上没有 ali-root 别名，使用配置了 SSH 密钥的 root@47.94.44.152。

WebUI 令牌保存在 VPS 的 `/root/qq-bot-napcat/credentials.json`（仅 root 可读）。在自己的终端读取：

```bash
ssh ali-root 'cat /root/qq-bot-napcat/credentials.json'
```

输入令牌后扫码登录 QQ。凭据、二维码和 QQ 数据不要提交到仓库或公开分享。容器运行健康仅说明管理页可用，不代表 QQ 已登录或机器人功能已接入。

## 数据与网络

| VPS 路径 | 用途 |
| --- | --- |
| /data/qq-bot/napcat/qq | QQ 登录状态与账号数据 |
| /data/qq-bot/napcat/config | WebUI、OneBot、NapCat 配置 |
| /data/qq-bot/napcat/plugins | NapCat 自身插件；业务插件以后由独立功能容器管理 |

宿主仅发布 127.0.0.1:6099。OneBot WebSocket 3001 只在容器网络内监听，有独立随机令牌；接入功能容器时连接 NapCat 所在网络并核对实际网络别名。未开放公网 OneBot 或新增域名。

配置以 Coolify 中的 Compose 为线上来源，本地 compose.yaml 保留部署副本。现有配置下，WEBUI_TOKEN、MODE 等初始化变量不会覆盖已有配置；后续设置优先在 WebUI 修改。

## 日志与开关

在 Coolify 的 NapCat 资源页单独 Start / Stop / Restart，子容器 Logs 查看运行日志。日志轮转为 10 MiB × 3。此处运行日志不等同于完整 HTTP 访问审计或 QQ 消息归档；本次没有添加独立日志服务。

日志可能包含登录二维码链接、令牌和消息内容，分享前自行脱敏。日志轮转只约束 Docker stdout/stderr，不包含 QQ 数据及应用自行生成的文件。

## 镜像与更新

官方镜像 mlikiowa/napcat-docker:v4.18.41，本次拉取 digest：sha256:b101b8968cc31ae428ec0f8e117386e4ced7773b2d8226ed9f7ddfcec55f1b7e。

VPS 当前无法直连 Docker Hub，因此本机拉取官方镜像后通过 docker save / SSH / docker load 导入。Compose 使用 pull_policy: never；重新部署使用已导入镜像。不要直接点击拉取最新镜像，先将目标版本导入 VPS，再修改 Compose 版本。

升级前停止 NapCat 并备份上述三个目录及 root 凭据文件到私有存储，保留旧镜像。回退时停止服务、改回旧镜像；如版本改变了配置或数据格式，还需恢复对应备份。未配置定时或异机备份。

官方参考：https://github.com/NapNeko/NapCat-Docker

## 本次核验

2026-10-23：docker compose config --quiet 通过；Coolify 启动请求成功；Docker health 为 healthy；GET /webui/ 返回 HTTP 200；实际 NapCat.Core 版本 4.18.41。已核对回环端口、三个挂载和 Docker 日志轮转，启动后重启次数为 0。

导入 VPS 后的镜像配置 ID 为 sha256:045cb917c7d6f0147447eb272902a153f51e8cbdb1dc0e6df270ebd4253b4337；docker save/load 不保留 RepoDigests，因此部署固定版本标签并禁止自动拉取，原始仓库 digest 单独记录在上文。

未验证 QQ 扫码登录、消息收发、功能插件、实际停止/重启、备份恢复。检查期间 ABL 存在其他部署活动；本次未修改或重启共享代理及其他业务资源。

## 域名接入结果

2026-10-23已上线 https://napcat.secret-sealing.club/webui/，直连A记录47.94.44.152，Coolify代理目标为容器内6099。HTTP自动302到HTTPS，WebUI HTTP200、TLS校验通过、页面标题NapCat WebUI、容器healthy。证书由Let's Encrypt签发，到期2027-01-21，后续由Traefik管理续期，未演练续期。

由于现有HTTP跳转规则会拦截ACME验证，VPS `/data/coolify/proxy/dynamic/napcat-acme.yaml` 仅将本域名的 `/.well-known/acme-challenge/` 路径交给 `acme-http@internal`；需保留供续期使用。首次签发的临时路由已移出动态目录，不重启共享代理。原宿主回环端口保留用于排障，OneBot端口仍不发布。

## DeepGHS 手动识别原型

`prototype/deepghs-manual` 分支包含可选的DeepGHS推理引擎和 `/色图识别` 手动入口，未部署线上。模型来源、启动方式及开发机CPU基准见 [原型说明](docs/deepghs-prototype.md)。权重不随Git提交。
