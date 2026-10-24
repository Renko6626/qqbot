# DeepGHS 手动图片分级原型

本原型只包含本地CPU推理引擎与手动识别插件，位于 `prototype/deepghs-manual` 分支。未部署VPS，不包含群自动监控、撤回、禁言、样本收集或WD14。

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
# .env 设置管理员密码；无需QQ时将 BOT_ONEBOT_URL 留空
uv run --extra nsfw --env-file .env python -m qqbot.app
```

`BOT_DEEPGHS_MODEL_PATH` 默认 `data/models/deepghs_rating/model.onnx`；`BOT_DEEPGHS_THREADS` 默认1，可设2。当前引擎为ONNX Runtime1.31.0，位于nsfw可选依赖中，普通安装不会带入该运行时。模型在第一次识别时创建CPU InferenceSession并复用，加载和推理在线程中执行，同一引擎串行使用会话；没有新增任务队列或常驻服务。

使用CPUExecutionProvider、SEQUENTIAL、全图优化，intra线程按上述环境变量设置、inter线程固定1，两类线程自旋均关闭。固定模型的batch/height/width设为1/384/384，并校验输入float32 NCHW及三分类输出。预处理与概率返回方式保持原样。只支持ONNX文件；旧OpenVINO XML/BIN不能作为模型路径。升级现有开发环境运行`uv sync --extra nsfw`，uv会移除OpenVINO并安装ORT；不需要重新下载同一份ONNX权重。

管理页会自动发现“图片分级（DeepGHS）”，默认关闭且无授权范围。配置允许群或私聊用户并启用后，使用 `/色图识别` 或 `/识别色图`，支持同条附图、回复图及提示后补图。白名单、群参数覆盖和插件日志复用宿主设施。

回复包含三个分数、最高分标签、纯推理及图片处理耗时，下载耗时不包含在后者。首次调用另外注明加载耗时。动图仅看首帧并明确提示；不把首帧结果解释为全部动画安全。默认下载10MiB、400万像素，超过上限给出提示。

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

`pytest -q` 34项通过（现有Starlette/httpx弃用提示保留）。测试包含官方归一化、透明底、RGB透明颜色键、缩放前EXIF方向校正、输出不重复Softmax、像素边界、动图首帧提示和真实ORT小图运行/复用。小图为仓库内无权重的ReduceMean→Softmax ONNX夹具，重建说明见`tests/fixtures/generate_rating_model.py`；运行测试不需要安装onnx模型制作库。官方固定模型已本地通过ORT完整处理路径运行。所有插件可加载，而ORT模块和模型不会随插件发现自动加载。

尚未部署或在实际QQ群内测试手动收发，未针对真人图或群内真实图片校准。当前Dockerfile按默认requirements.lock构建，不包含nsfw可选运行时，本原型按上面的uv命令运行；上线前需要确认可选依赖的容器构建方式、模型持久化挂载及测试群。
