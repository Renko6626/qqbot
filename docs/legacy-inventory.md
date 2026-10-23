# /root/mybot 迁移清单

2026-10-23，经 ali-root 只读检查。三个 NoneBot 项目：bfv、Renko_1055、yrxnb。没有发现 cwd 或 Python 启动参数指向 mybot 的运行进程；PM2 保存清单也未含这些项目。此结论不代表检查了所有外部启动方式。

| 插件 | 已识别用途 | 迁移处理 |
| --- | --- | --- |
| bfvtest | 连接检查 | 新底座重新实现小命令 |
| rule_chat | 帮助 | 根据实际加载与权限生成，移除手写旧功能列表 |
| whitelist | 分功能群白名单与管理命令 | 由已确认的管理页和公共配置替代，业务插件不依赖另一个业务插件 |
| title_manage / title_giver | 群头衔 | 两份近似实现，均引入 OpenAI 审核；确认要保留的行为后合并，暂不带入 |
| random_meme | 随机图片、加解密 | 先拆分用途，再迁移用户选定的图片分类；不整包带入 cv2 和同步 requests |
| image_processer | GIF/图片变换 | 带 Pillow、OpenCV、numpy，后续逐项选操作 |
| my_essence | 精华消息备份、查询、排名与导出 | 有 SQLite 与媒体资源，需单独核对数据路径和保留范围 |
| getmembers | HTTP触发群成员导出 | 特殊管理工具，待确认是否保留；不直接公开旧接口 |
| hifuu_images | 上传、随机图、去重与以图搜图 | ONNX、FAISS、SQLite 混合；普通图库与向量检索应分别考虑 |
| nailoong_identify | 图片分类、群监控、撤回和样本上传 | OpenVINO、OpenCV 等重依赖，有主动群管理行为，暂缓 |
| nailoong_story | AI故事 | 暂缓 |
| nailoong_zimage | 外部文生图、额度记录 | 暂缓，保留需求时再独立评估 |
| hecate_system | 外部AI后端会话、状态与重载 | 暂缓 |
| renko_bot | AI角色、上下文与消息数据库 | 暂缓；入口第29行有语法错误，不能沿用“已打通”注释作验收 |
| touhou_terminator | RAG、OCR与问答 | 暂缓，涉及 ChromaDB、Kuzu、多个模型服务 |
| yrxnb/deport | 表情回应达到阈值后提醒和尝试禁言 | 需用户明确保留行为后才迁移，默认不启用 |
| yrxnb/probe | 原始事件日志 | 调试用途，默认不迁移全量消息记录 |

bfv目录约1.1GB，包含虚拟环境、模型、数据库及图片。pyproject.toml 未完整声明运行依赖；旧 .env 含访问令牌与服务密钥，未复制、未记录值。bfv/bot.py 有旧 src/plugins 路径和未导入 logger 等残留，旧 PM2 ecosystem 文件指向曾经的虚拟环境和 NapCat 路径。新底座显式加载插件，不自动导入整棵旧目录。

后续每次迁移核对：触发命令、群权限、数据资源、第三方调用、是否会撤回/禁言、实际所需依赖。旧目录本次保持不变。
