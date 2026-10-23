# 2026-10-23 SSH 手动运维核验

用户确认后创建私有仓库 `Renko6626/qqbot`，默认分支main，无CI与自动发布。VPS专用部署密钥ID167427630，只读；私钥仅在 `/root/qq-bot-nonebot/github_readonly`，使用仓库级SSH配置和GitHub443端口，未修改全局SSH配置。

## 已执行

- 源码提交与推送前检查：`.env`、虚拟环境、`.qoder` 均被忽略；暂存源码不含本地管理员密码。
- `uv run pytest -q`：7 passed，有1条上游Starlette/httpx弃用提示。
- `bash -n ops/nonebot.sh`、脚本help与JS语法检查通过。
- 导入原Python基础镜像的本地副本 `qqbot-python:3.13-20261023`，VPS可访问PyPI。
- VPS实际只读clone到 `/opt/qqbot`，执行 `bash ops/nonebot.sh backup` 和 `update`。git pull --ff-only及服务器Docker构建成功；构建时原容器仍在运行。
- 生成镜像 `qqbot:git-68485715766acf5f30fbd9456f6dc05b9d68168a`，镜像ID `sha256:4d0f68f17ee94c0ad796b54c30ccbdf192531bec37517b60d080e9b0f66cf78a`；构建成功后qqbot:manual指向该镜像。
- 通过Coolify官方API保存manual镜像的Compose，再调用资源Restart，核实其确实重建容器并使用新镜像。没有直接docker compose up。
- 重建后健康状态healthy，运行源码标签与上述提交一致，HTTPS `/healthz` 和带当前管理员认证的 `/api/status` 均200，连接1个QQ账号。
- 发布前后插件JSON哈希一致、NapCat容器ID一致；未发送QQ消息或操作群管理。

配置备份：`/root/qq-bot-nonebot/backups/nonebot-20261023T130227Z.tar.gz`。构建日志：`/root/qq-bot-nonebot/manual-build.log`。发布前核对记录：`/root/qq-bot-nonebot/manual-ops-before.json`。这些属于VPS私有运维资料，不作为运行配置来源。

独立只读审阅未发现本次脚本和运维路线的重要错误。未演练回退旧运行版本、归档恢复或证书续期；没有新增自动备份、自动清理或云端工作流。

后续纯文档提交可能晚于运行提交，属于正常情况；运行版本以 `ops/nonebot.sh status` 输出为准。
