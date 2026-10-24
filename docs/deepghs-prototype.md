# DeepGHS 图片识别与自动监测

功能已合入`main`并部署，提供本地CPU推理、手动识别和自动监测两个插件。自动监测仅保存命中图片，并可配置回复。发布详情见[部署记录](deepghs-deployment.md)。不包含撤回、禁言或WD14。

## 模型与使用依据

- 官方模型仓库：[deepghs/anime_rating](https://huggingface.co/deepghs/anime_rating)，模型卡标注MIT许可，任务面向动漫图片的粗粒度分级。
- 固定变体 `mobilenetv3_sce_dist`，它是MobileNetV3蒸馏版，不等同于imgutils当前默认的其他变体。
- 固定revision：`46be80bfe01a415efa5aa7c025528cac82a8b88a`。
- `model.onnx`：16,827,558 bytes，SHA-256 `31814ba076d65d129b89322a767d55d0669c54015134c117da3cf2717defde4e`。
- [固定meta.json](https://huggingface.co/deepghs/anime_rating/blob/46be80bfe01a415efa5aa7c025528cac82a8b88a/mobilenetv3_sce_dist/meta.json)规定输出顺序 `safe / r15 / r18`。该变体没有单独preprocess.json，按上游[generic/classify.py](https://github.com/deepghs/imgutils/blob/main/imgutils/generic/classify.py)回退流程：白底RGB、双线性resize到384×384、CHW、像素除255后使用mean=.5/std=.5，输入NCHW float32。
- 旧服务使用ImageNet mean/std，且对已经Softmax的输出再次Softmax；原型已修正这两点。引擎直接校验并返回模型概率，不另加风险加权公式。
- 模型输出是模型预测分布，适用性限于该任务；真人照片效果未评估，本次没有准确率或误判率评测。模型卡也将边界判断定位为粗略估计，不据此直接执行群管理动作。

权重保存在Git忽略的data目录，不提交到公开仓库；下载脚本锁定来源、大小与哈希，不在机器人启动时自动联网获取模型。

## 本地启动

```bash
uv sync --extra nsfw
uv run python ops/fetch_deepghs_model.py
uv run python ops/fetch_deepghs_model.py --kind gate
# .env 设置管理员密码；无需QQ时将 BOT_ONEBOT_URL 留空
uv run --extra nsfw --env-file .env python -m qqbot.app
```

`BOT_DEEPGHS_MODEL_PATH` 默认 `data/models/deepghs_rating/model.onnx`；`BOT_DEEPGHS_THREADS` 默认1，可设2。当前引擎为ONNX Runtime1.31.0，位于nsfw可选依赖中，普通安装不会带入该运行时。模型在第一次识别时创建CPU InferenceSession并复用，加载和推理在线程中执行，同一引擎串行使用会话；没有新增任务队列或常驻服务。

使用CPUExecutionProvider、SEQUENTIAL、全图优化，intra线程按上述环境变量设置、inter线程固定1，两类线程自旋均关闭。固定模型的batch/height/width设为1/384/384，并校验输入float32 NCHW及三分类输出。预处理与概率返回方式保持原样。只支持ONNX文件；旧OpenVINO XML/BIN不能作为模型路径。升级现有开发环境运行`uv sync --extra nsfw`，uv会移除OpenVINO并安装ORT；不需要重新下载同一份ONNX权重。

管理页自动发现两个独立入口，均默认关闭且无授权范围：

| 功能 | 插件ID | 使用方式 |
| --- | --- | --- |
| 手动图片识别（DeepGHS） | `anime_rating` | `/色图识别`或`/识别色图`，支持附图、回复图及提示后补图 |
| 自动图片监测（DeepGHS） | `anime_rating_watch` | 检查已授权群的新图片，命中后保存，并按配置回复 |

手动插件保留原ID及已有配置，支持群聊与已授权私聊。自动插件仅处理群聊新图片，不扫描历史记录或被回复消息中的图片。两个插件分别配置开关、群/用户白名单、公共参数及群覆盖；修改参数下次处理时生效。“启动时加载”修改后需重启NoneBot。自动功能无需出现在`/帮助`的命令列表中。

回复包含三个分数、最高分标签、纯推理及图片处理耗时，下载耗时不包含在后者。首次调用另外注明加载耗时。动图仅看首帧并明确提示；不把首帧结果解释为全部动画安全。默认下载10MiB、400万像素，超过上限给出提示。

## 自动监测配置与归档

用户已选择命中规则：`scores.r15 + scores.r18 >= threshold`，默认`threshold=0.8`。阈值在管理页可调，支持群覆盖；未用真实群图片校准，不能把模型分数当作人工审核结论。

- `threshold`：r15+r18命中阈值，0到1，默认0.8。
- `gate_threshold`：二维闸门阈值，默认0.9。闸门先要求最高类别属于动画截图、漫画、插画，再要求这三类概率合计达到阈值；预测最高类别为3D或非绘画时始终跳过。支持群覆盖，与后面的分级阈值独立，已有`threshold`配置保持不变。
- `reply_text`：命中回复文字，默认“我吃！”。回复依次包含引用原消息、该文字、`milly_cat.jpg`猫猫表情包，组成同一条消息。文字可在管理页修改；留空则仅保存，也不发送表情包。已有配置若显式保存了空文案，需要在管理页填写“我吃！”才会开启回复。
- `max_download_mb`、`max_pixels`：该插件自己的图片限制，默认10MiB和400万像素，与手动插件独立配置。

多图消息逐张处理，只保存命中项；至少成功保存一张且配置了回复文案时，每条消息回复一次。未命中不保存、不回复。超限或识别/保存失败记录该插件日志并跳过。手动识别命令不进入自动监测；手动提示后的补图由优先级更高的会话处理，避免重复触发。

二维闸门已经接入本分支的自动路径，尚未发布线上。未通过时不运行分级模型，也不保存或回复；缺少闸门模型同样跳过，不回退到未过滤的自动识别。手动`/色图识别`继续直接返回原始分级，不要求闸门模型存在。离线样本及边界见[闸门实验](anime-gate-experiment.md)。普通二维表情包仍可能通过，闸门不替代内容分级。

表情包位于`qqbot/plugins/anime_rating_watch/assets/milly_cat.jpg`，由用户原图972×972压缩至512×512，100,192字节降至30,443字节，并去除原始EXIF元数据。资源随`qqbot`目录进入容器，通过OneBot Base64图片消息发送，无需协议端访问NoneBot容器内路径。

归档根目录通过`BOT_DEEPGHS_ARCHIVE_DIR`设置，默认`data/anime_rating_hits`，必须放在需要保留的持久化目录内。目录结构为`<根目录>/<群号>/<UTC日期>/<消息号>-<随机ID>.<扩展名>`，同目录下有同名JSON。图片保留下载原始字节，不另行压缩；JSON记录时间、群号、消息号、文件名/格式、分级标签、三个分数和是否只识别首帧，经过闸门的命中另有`gate`对象记录类型标签和五类分数。不保存完整聊天正文、用户昵称或下载URL。使用随机ID避免同条多图相互覆盖，不做内容去重。归档可按日期目录手工查看和清理，当前没有自动保留期。

## 共用服务

`qqbot/image_rating/`负责推理引擎、输入上限、下载及线程调用；两种插件调用同一个`service.analyze_image`。分级与闸门各复用一个ORT会话，默认各单线程，自动路径只下载、解码和归一化一次，共用同一份张量，先运行闸门再分级。手动插件仅负责命令和结果展示，自动插件负责命中判断、归档及回复；业务插件不互相导入处理器。关闭任一插件不影响另一插件的权限或处理。发现声明和加载插件均不创建模型会话，首次实际识别才加载。透明PNG仍沿用已验证的先白底合成再缩放路径。

闸门路径可通过`BOT_DEEPGHS_GATE_MODEL_PATH`设置，默认`data/models/deepghs_gate/model.onnx`。发布本分支前，须先把通过固定哈希校验的权重放到VPS挂载目录`/data/qq-bot/nonebot/models/deepghs_gate/model.onnx`，保持容器UID1000可读，再按原SSH构建/Coolify Restart流程发布。当前线上仍是仅分级的旧版本。

## 历史OpenVINO开发机CPU数量级

本轮依用户要求只在开发机测量，没有在忙碌的VPS上加载或运行模型。开发机为Intel Xeon Gold 6330 @2.00GHz，112个逻辑CPU可见；OpenVINO2026.4.1、Python3.13.2。每次限制1或2个推理线程、1 stream、batch=1、384×384 float32，串行请求；5次预热，各测50次。两个线程配置分别启动独立进程，避免冷启动和内存结果互相污染。

输入为本地生成的512×512 RGB渐变PNG，不含敏感内容。纯推理复用预处理张量，完整图片处理包括解码、预处理及推理，均不含下载、QQ通信或排队。

| 配置 | 纯推理均值 / 吞吐 | 含解码预处理均值 / 吞吐 | 处理P95 | 暖机RSS |
| --- | --- | --- | --- | --- |
| 1线程 | 17.3ms / 57.9张每秒 | 28.4ms / 35.2张每秒 | 39.1ms | 181.4MiB |
| 2线程 | 9.1ms / 110.0张每秒 | 24.2ms / 41.3张每秒 | 30.2ms | 181.6MiB |

模型读取/编译约0.34–0.38秒（脚本提前导入运行时，不含Python启动/导入耗时）。独立进程VmHWM约182MiB，包含Python/OpenVINO和图片处理，不能当作权重大小或直接当作NoneBot容器总内存。本环境getrusage高水位与/proc实际进程指标不一致，因此脚本使用/proc/self/status的VmRSS/VmHWM。

前一轮同机结果为单线程纯推理约46–50张/秒、图片处理约29–31张/秒，反映共享开发机调度波动。可据此判断为**每张几十毫秒、每秒几十张**的图片处理数量级；VPS只有2个vCPU且微架构/负载不同，不能按开发机数据承诺线上吞吐量。默认仍建议单线程用于低频手动调用。

以下命令当前用于测量ORT（两个独立进程）；本节历史OpenVINO数字保留为优化前记录，需用旧提交`a4eb085`及其依赖复现。两种引擎的近期对照使用[独立比较脚本](deepghs-runtime-comparison.md)。

```bash
uv run --extra nsfw python ops/benchmark_deepghs.py --threads 1 --iterations 50 --warmup 5 --output /tmp/deepghs-cpu1.json
uv run --extra nsfw python ops/benchmark_deepghs.py --threads 2 --iterations 50 --warmup 5 --output /tmp/deepghs-cpu2.json
```

原始记录：[1线程](benchmarks/2026-10-24-deepghs-cpu1.json)、[2线程](benchmarks/2026-10-24-deepghs-cpu2.json)。这组测试验证运行路径与耗时，不验证识别准确性。

## 解码和预处理优化

普通RGB图片跳过RGBA转换和整图白底合成；RGB PNG带透明颜色键时仍保留白底处理。识别路径在图片文件关闭前原地处理EXIF方向并缩放，省去原来的原尺寸副本；RGBA、调色板等输入沿用原有白底合成。保持Pillow双线性384×384、RGB通道、NCHW和float32，归一化按原顺序原地执行，减少中间数组。没有更换运行时、缩放算法或增加并发机制。

同一开发机对照优化前提交`a4eb085`，每个样本预热3次，交替执行新旧路径各30次，只计解码和预处理，不含下载或推理：

| 合成输入 | 优化前 | 优化后 |
| --- | --- | --- |
| 512×512 RGB PNG | 13.94ms | 9.50ms |
| 512×512 JPEG | 12.00ms | 7.12ms |
| 1600×1200 JPEG | 45.12ms | 18.80ms |
| 1600×1200 RGBA PNG，alpha=128 | 73.15ms | 73.84ms |

样本为坐标渐变图，所有计时样本新旧输出张量逐位一致；另对L、LA、P、CMYK输入完成张量对照。透明PNG本轮没有明显收益。共享开发机有调度波动，这些数字不代表真实QQ群图片分布或VPS性能。原始记录：[预处理对照](benchmarks/2026-10-24-deepghs-preprocessing.json)。此前的完整推理基准保留为优化前记录，不能与本表直接相加推算吞吐。

后续[大透明PNG实验](transparent-png-experiment.md)比较了RGB白底paste与先缩小RGBA两条候选；默认路径尚未接入这两项实验。

## 验证与当前边界

优化后的OpenVINO与ONNX Runtime开发机对照见[运行时比较](deepghs-runtime-comparison.md)。用户确认后，原型已切换到ORT单线程；项目nsfw依赖不再包含OpenVINO。

`pytest -q` 44项通过，保留Starlette/httpx及NoneBot ForwardRef弃用提示。测试包含官方归一化、透明底、RGB透明颜色键、缩放前EXIF方向校正、输出不重复Softmax、像素边界、动图首帧提示和真实ORT小图运行/复用。新增插件验证复用真实ORT小模型、模拟HTTP图片响应和NoneBot处理器，覆盖未命中不写文件、命中原图和JSON、空文案、同条多图只回复一次、群参数覆盖、独立权限及保存失败不回复；没有连接真实QQ。新接入验证还覆盖3D/非绘画短路、闸门缺失不绕过和手动识别不依赖闸门。小图为仓库内无权重的分级与五分类ONNX夹具，重建说明见`tests/fixtures/generate_rating_model.py`；运行测试不需要安装onnx模型制作库。官方固定模型已本地通过ORT完整处理路径运行。所有插件可加载，而ORT模块和模型不会随插件发现自动加载。

已部署VPS并验证健康、模型和QQ连接；尚未在实际QQ群内测试手动收发，未针对真人图或群内真实图片校准。Docker通过requirements.lock安装包含nsfw的生产依赖；模型保存在持久化data/models/deepghs_rating/model.onnx，归档保存在同一数据卷的anime_rating_hits目录。本地开发仍可用uv的nsfw可选依赖安装方式。实际QQ群收发留待发布后验证。
