# SSH 手动运维实施记录

用户已确认：私有Renko6626/qqbot，VPS专用只读部署密钥，SSH手动pull和构建，无CI。保留Coolify控制进程和发布，NapCat独立。

- [x] 整理账号密码、Locked、配置生效、重启、发布与回退文档。
- [x] 实现ops/nonebot.sh：update/build/status/logs/backup/promote，构建不自动重启，提交号镜像加manual发布标签。
- [x] 初始化Git并发布不含秘密的源码，配置只读SSH拉取。
- [x] 预装原Python基础镜像，在VPS实际pull和构建。
- [x] Coolify采用manual标签，重建NoneBot并验证健康、管理认证及QQ连接；核对NapCat未重启。
