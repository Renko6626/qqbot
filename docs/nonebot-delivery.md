# 2026-10-23 NoneBot 底座与管理页交付

以下记录首次交付状态。后续已按用户确认接入私有仓库和VPS手动构建，当前操作以 [运维手册](nonebot-operations.md) 为准，实际执行记录见 [SSH运维核验](manual-operations-verification.md)。

## 已完成

NoneBot与原NapCat作为同一Coolify项目的独立资源。用户确认的FastAPI、原生前端、单JSON配置和独立管理员账号密码已实现。一个进程提供OneBot客户端和管理页，Coolify管理容器生命周期。

现有插件仅连接检查、帮助；默认关闭且群列表为空。没有整包复制旧代码、模型、数据库、图片和密钥，没有迁移AI/RAG。旧目录保持原状，后续迁移按清单逐项决定。

管理页：https://bot.secret-sealing.club/ 。服务UUID `8hzqwaltqvmjo73d5lkv2rll`，镜像 `qqbot:20261023-1`。配置持久化 `/data/qq-bot/nonebot`，初始管理员凭据在本地被忽略的 `.env`，服务器root私有副本 `/root/qq-bot-nonebot/credentials.json`。不把凭据写入交付说明。

## 实际验证

- `uv run pytest -q`：7 passed，覆盖配置持久化、真实权限判断、加载改变需重启、认证、保存与输入校验。测试运行有一条上游Starlette对httpx测试客户端的弃用提示，未导致失败。
- `node --check qqbot/static/admin.js`：成功。
- 本地 `python -m qqbot.app` 实际启动，两个插件成功加载；Docker镜像实际启动，health200、未认证管理API401、未使用OneBot入站路径404。
- 桌面1440px与手机390px页面截图查看；未自动点击、填写表单或运行交互流程。页面脚本无异常，手机页面宽度390px，无横向溢出。
- 线上未经认证HTTPS401，携带管理员认证的首页、状态API、插件API均200。状态API读取到1个QQ连接；两个插件loaded=true、enabled=false、restart_required=false。
- HTTP302到HTTPS；TLS验证通过，Let's Encrypt证书有效至2027-01-21 11:04:07 UTC。验证路径通过域名限定的HTTP ACME路由交给Traefik内部服务。
- 容器healthy，宿主仅127.0.0.1:18089映射8080。独立服务网络与NapCat内部网络均已接入。一次空闲采样约47MiB内存，仅是此时样本，不是性能基准。

独立代码审阅未发现阻断问题；其提出的可选Coolify链接格式错误导致页面加载中断问题已局部修正。

## 未验证与后续

未在生产自动启用功能、发送QQ消息、修改群权限、撤回或禁言。未演练生产重启后配置保留、备份恢复和证书续期；配置跨重启语义已由真实文件读写测试覆盖。插件的实际QQ行为由用户选定范围后使用核对。

尚未创建GitHub远程仓库或CI。发布方式是本机构建、镜像经SSH导入VPS，再由Coolify部署。源码、配置和运维说明保留在当前目录；不会自动拉取镜像更新。
