# QQ Bot 运维手册

适用：ali-root（47.94.44.152）上的 QQ Bot 项目。源码公开仓库：<https://github.com/Renko6626/qqbot>。当前采用 SSH 手动更新和服务器构建，Coolify 负责发布、启停与日志；没有自动部署或 CI。

## 日常入口

| 用途 | 入口 |
| --- | --- |
| 插件开关与配置 | https://bot.secret-sealing.club/ |
| QQ 登录与协议设置 | https://napcat.secret-sealing.club/webui/ |
| 进程、变量和日志 | https://coolify.secret-sealing.club/ |

Coolify 路径：QQ Bot → production → NoneBot（功能容器）或 NapCat（基础设施）。[直接打开 NoneBot 资源](https://coolify.secret-sealing.club/project/zedd9kjkwxycw6qtsf43f8gv/environment/zi47jjycv0tz997e8bvzzzrg/service/8hzqwaltqvmjo73d5lkv2rll)。

## 登录与修改密码

bot 管理页使用浏览器自带的 HTTP Basic 登录框，当前只有一个管理员。初始用户名为 admin，初始密码在本地 `.env` 中；VPS 的 `/root/qq-bot-nonebot/credentials.json` 是初次部署的私有副本。**这两份副本不会自动跟随改密更新，线上始终以 Coolify 环境变量为准。**

1. 打开 NoneBot → Environment Variables。
2. 修改 `BOT_ADMIN_USER` 或 `BOT_ADMIN_PASSWORD`，保存。
3. 返回 NoneBot 资源页，点击右上角 **Restart**。
4. 等待容器 Running / Healthy，用新的隐私窗口打开 bot 管理页，输入新账号密码。
5. 自行更新需要保留的本地密码记录。修改本地 `.env` 不会修改线上密码。

BOT_ADMIN_PASSWORD 现在是可编辑变量。初次部署曾设为“仅显示一次”，导致显示 Locked，现已解除该标记，密码值未改。BOT_ONEBOT_TOKEN 仍保持 Locked，它是 NapCat 内部连接令牌，与管理页密码无关。不要为了改管理密码去修改该令牌。

遗忘管理密码时，通过 Coolify 重新设置即可；没有注册、多用户、页面内改密或 Coolify 单点登录。浏览器会缓存 Basic 凭据，关闭专用隐私窗口可结束这次浏览器会话；修改线上密码可使旧凭据失效。只通过 HTTPS 输入凭据。

## 插件配置何时生效

管理页顶部的“重启 NoneBot 进程”使用方案A：响应请求后发送SIGTERM正常退出，由现有Docker unless-stopped策略拉起同一个容器。它会重新读取已保存的插件配置和加载选择，短暂中断管理页与QQ连接。网页会检查新的进程启动时间，最多等待约30秒，不重复发重启请求；未恢复时可刷新或到Coolify检查日志。

有未保存修改时，页面会要求先保存。若NoneBot无法启动，管理页也不可用，继续使用Coolify修复。进程重启不会切换镜像或重新读取Coolify中尚未应用的环境变量。

| 操作 | 生效方式 |
| --- | --- |
| 全局功能开关、允许的群、私聊开关、插件参数 | 管理页保存后对新消息生效 |
| 启动时加载 | 保存后点击网页“重启 NoneBot 进程”，下次启动时生效 |
| Coolify 环境变量 | 保存后点击 Coolify Restart，重新生成环境并重建容器 |
| 新代码或依赖 | 先构建镜像，再点击 Coolify Restart |

“功能关闭”不会卸载已经导入的插件；“不在启动时加载”可在重启后避免导入它的依赖。正在执行的处理不会取消。空群列表表示不在任何群响应，私聊需单独开启。第一版提供 `/测试连接` 和 `/帮助`，两个插件分别开关。

每个群可选全群成员或指定成员。指定成员名单为空表示该群无人可用。私聊可关闭、允许所有用户或仅指定用户，空私聊白名单同样拒绝所有用户。网页的“按群查看”汇总同一份已保存配置，不另存权限表；“权限预览”输入插件、群（留空为私聊）和QQ号后显示实际允许或拒绝原因，包含当前加载和启用状态。

加载失败与待重启分别显示：失败需看日志修正，重复重启不会自动修复代码。旧配置会保留原有的全群成员和全部私聊用户语义，用户可以再按需要收紧。

## SSH 更新、构建与发布

服务器源码固定放在 `/opt/qqbot`，仅此目录执行 git pull。运行数据在另一个目录，不随代码覆盖。VPS 只读部署密钥只对这个仓库有效，不承担推送权限。

本地修改后先运行受影响的检查，提交并推送 main：

```bash
uv run pytest -q
node --check qqbot/static/admin.js
# 检查改动，不要提交 .env 或业务数据。
git add <本次修改的文件>
git commit -m "说明本次修改"
git push origin main
```

在服务器执行：

```bash
ssh ali-root
cd /opt/qqbot
bash ops/nonebot.sh backup
bash ops/nonebot.sh update
```

`update` 执行 `git pull --ff-only`，从干净的提交构建 `qqbot:git-<完整提交号>`，构建成功后把 `qqbot:manual` 指向该镜像。构建失败时不会切换这个标签，也不会主动停止当前服务。构建时机器会消耗CPU和磁盘，尽量避开其他项目发布。

然后到 Coolify 的 **NoneBot** 资源点击 **Restart**。其 Compose 固定使用 `qqbot:manual`、`pull_policy: never`，因此会用刚构建的本地镜像重建容器，不去远程仓库拉取。不要点 Pull Latest Images，不要在服务器手动 docker compose up，不要重启 Docker、共享代理或 NapCat。

```bash
# 已经 git pull 过，只构建当前提交：
bash ops/nonebot.sh build
# 查看健康、当前镜像ID和运行源码提交：
bash ops/nonebot.sh status
# 实时查看日志，Ctrl+C退出：
bash ops/nonebot.sh logs
```

镜像构建不是自动发布，`qqbot:manual` 只是下次重建的目标。页面暂时仍是旧行为时，先看 status 的运行提交与本次构建输出是否一致，再检查是否已点击 Restart。不能只看 main 或本地镜像标签判断运行版本。

## Python 基础镜像与依赖

VPS 目前不能直连 Docker Hub，但已验证可访问 PyPI。已预装与原部署相同的 Python 基础镜像，本地标签为 `qqbot-python:3.13-20261023`。更新脚本显式使用该本地镜像，不尝试拉取基础镜像。

Dockerfile 的默认值仍固定官方 Python 镜像 digest；`PYTHON_IMAGE` 构建参数仅用于选择已预装副本。换服务器或基础镜像丢失时，在能访问 Docker Hub 的本机执行：

```bash
docker pull python:3.13-slim@sha256:e5c5e1775e212d259fa017226b2719de00a8c134335a0d4bc538dc6727984353
docker tag python:3.13-slim@sha256:e5c5e1775e212d259fa017226b2719de00a8c134335a0d4bc538dc6727984353 qqbot-python:3.13-20261023
docker save qqbot-python:3.13-20261023 | gzip -1 | ssh ali-root 'gunzip | docker load'
```

首次构建需从 PyPI 下载已锁定依赖，后续 Docker 缓存可复用。依赖改变时更新 pyproject.toml、uv.lock 和 requirements.lock；不要在运行容器中 pip install。不要为了这个项目修改全局 Docker 镜像源或代理配置。

## 回退

先选定上一版镜像，不改配置和业务数据：

```bash
cd /opt/qqbot
docker image ls qqbot
bash ops/nonebot.sh promote qqbot:git-<上一版完整提交号>
# 初始版本也保留为 qqbot:20261023-1。
```

再在 Coolify 点 NoneBot 的 Restart。`promote` 仅切换 `qqbot:manual` 指向，不触发部署，不自动回退数据格式。如新版改变了JSON结构，需要同时选择相应备份并人工恢复。

新增用户白名单字段在首次网页保存时写入JSON；旧镜像不能识别这些新字段。若回退到不支持白名单的旧版本，需要在停机后同时恢复升级前配置备份，不能直接带新JSON启动旧代码。

平台或人工磁盘清理可能移除未使用的旧镜像。若所选镜像已不存在，可检出旧提交重新构建，再切换发布；操作结束后把源码工作区切回main，避免下次pull处于分离HEAD。

`backup` 仅备份 `/data/qq-bot/nonebot` 到 `/root/qq-bot-nonebot/backups/`，权限仅root可读。若恢复配置，先在Coolify停掉NoneBot，再核对归档内容并恢复到原目录，保留UID:GID1000:1000，最后启动。不要把旧备份直接覆盖正在写入的配置。当前没有自动清理备份、定时备份或异机备份。

## 目录与职责

| VPS 路径 | 内容与所有权 |
| --- | --- |
| /opt/qqbot | Git源码，只从仓库更新，不放运行秘密和业务数据 |
| /data/qq-bot/nonebot | 插件配置plugins.json与后续功能数据，容器UID/GID1000 |
| /root/qq-bot-nonebot | 部署密钥、已知主机、源码归档和初始凭据/备份，root私有 |
| /data/qq-bot/napcat/{qq,config,plugins} | NapCat登录状态、配置与自身插件，不由NoneBot更新脚本操作 |
| /data/coolify/services/8hzqwaltqvmjo73d5lkv2rll | Coolify生成的配置和.env，不手动编辑，不公开其中内容 |

Compose源文件 `compose.nonebot.yaml` 在仓库中；线上真正发布使用Coolify里保存的Compose。以后改端口、挂载或网络时，需要把确认后的Compose同步到Coolify，单独git pull不会自动更新它。不要把本地配置或初始凭据副本覆盖到Coolify变量。

## 网络、日志与排障

- NoneBot → NapCat：内部正向WS `ws://napcat-n4wkgdcd9fmbitucekxzuyk5:3001`，通过既有NapCat网络连接；不公开OneBot入站接口。
- NoneBot回环入口：127.0.0.1:18089。公网HTTPS由Traefik转到容器8080；`/healthz`仅表明管理进程存活，不代表QQ已连接。
- QQ未连接时先看NapCat是否登录，再看NoneBot日志；不要重复启动第二套旧机器人。
- stdout/stderr按10MiB×3轮转。日志可能含消息或其他运行内容，分享前脱敏。没有另建日志平台。
- 保留 `/data/coolify/proxy/dynamic/qqbot-acme.yaml` 与 napcat-acme.yaml，它们为各自域名提供HTTP证书验证路径。无需重启共享Traefik。

## 仓库访问维护

仓库已按用户要求从private转为public，其他机器可以直接使用 `git clone https://github.com/Renko6626/qqbot.git`，无需读取凭据。公开前检查了完整Git历史，未发现已知部署凭据或私钥/令牌模式。

现有VPS继续使用已验证的专用只读SSH部署密钥和GitHub443端口，原更新命令不变。密钥位置 `/root/qq-bot-nonebot/github_readonly`，已知主机文件 `/root/qq-bot-nonebot/github_known_hosts`。该仓库的 `.git/config` 单独设置SSH命令，不修改服务器全局SSH行为。

若遇仓库拉取权限错误，在GitHub qqbot仓库 Settings → Deploy keys 检查该公钥是否仍存在且为只读。密钥丢失后生成新的专用密钥、登记公钥、验证拉取，再删除旧登记；不要把私钥或本机GitHub令牌写入仓库。
