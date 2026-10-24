# 图片识别功能发布记录

2026-10-24已通过原有SSH构建、Coolify重启流程发布到VPS，管理入口为https://bot.secret-sealing.club/ 。PR #1已合并；本次运行代码提交为`1529291628899e55f386cdfe7a66f14b9d8510f6`。

## 已发布内容

- 手动图片识别`anime_rating`，命令`/色图识别`及`/识别色图`。
- 自动图片监测`anime_rating_watch`，命中条件为`r15+r18≥0.8`，可按群覆盖。命中成功保存后引用原消息回复“我吃！”和压缩猫猫图片，每条消息最多一次。
- 两者独立管理，共用ORT1.31.0 CPU单线程引擎。模型首次调用才加载，默认10MiB/400万像素cutoff。透明图沿用先合成白底再缩放的路径。

两个新插件均已加载，当前**功能关闭、允许群为空**。到管理页分别启用并添加群/用户白名单，保存后对新消息生效，无需再次构建或重启。未自动复制其他插件的白名单。

## 镜像和持久化

生产`requirements.lock`已按`uv export --extra nsfw --no-dev --format requirements-txt --output-file requirements.lock`导出，现有Dockerfile会安装ORT及依赖，仍通过哈希校验安装。

- 镜像标签：`qqbot:git-1529291628899e55f386cdfe7a66f14b9d8510f6`，`qqbot:manual`指向同一镜像。
- 镜像ID：`sha256:7bb778c33a2ca2ce98790e6f03e2068fb19aa7d12f6d3c2785a4686d9471378a`。
- 数据挂载保持`/data/qq-bot/nonebot:/app/data`，容器UID/GID1000。
- 模型：宿主机`/data/qq-bot/nonebot/models/deepghs_rating/model.onnx`，容器路径`/app/data/models/deepghs_rating/model.onnx`。本次从开发机传入已验证的固定权重，VPS再次核对SHA256 `31814ba076d65d129b89322a767d55d0669c54015134c117da3cf2717defde4e`。
- 归档默认在宿主机`/data/qq-bot/nonebot/anime_rating_hits/<群>/<UTC日期>`，首次命中时创建。模型和归档均不进入Git，更新源码不覆盖它们。

## 验证

开发机`pytest -q`40项通过。VPS新镜像在无网络、只读数据挂载的临时容器中通过一次固定模型推理，确认ORT CPU可用和30,443字节表情包资源完整；未做VPS吞吐量基准。

经Coolify API执行NoneBot服务Restart，关闭拉取远程镜像。切换后容器healthy，运行源码标签为上述提交，公网`/healthz`返回ok，认证管理API显示两个插件加载成功，QQ连接数为1。发布前后插件配置文件SHA256均为`9cb02ca8ac8a13d19c5f544743a837bd7dd2264152025b4fbaf6764c7186a0c9`，原权限和参数没有修改。SnowLuma启动时间保持`2026-10-24T02:45:47.872448952Z`，未重启协议端或共享代理。

没有在真实QQ群发送测试消息，未验证真实QQ图片收发或校准分级准确率。启用后先在选定测试群使用，并查看插件日志。

## 回退

发布前数据备份：`/root/qq-bot-nonebot/backups/nonebot-20261024T082529Z.tar.gz`，仅root可读。旧镜像仍保留，ID为`sha256:0c45b5571045ceb19e2978851652d6561572d3c5e382829b67c545e7261c7409`。

若配置仍与发布前相同，可在`/opt/qqbot`执行`bash ops/nonebot.sh promote sha256:0c45b5571045ceb19e2978851652d6561572d3c5e382829b67c545e7261c7409`，再通过Coolify重启NoneBot。新模型文件可以保留，旧代码不会读取。

用户在管理页保存新插件配置后，JSON会包含新插件ID，旧镜像无法直接读取；回退时须先停NoneBot、核对并恢复上述配置备份，再启动旧镜像，注意保留升级后的其他配置变更。不直接覆盖运行中的配置。
