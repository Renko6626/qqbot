# DeepGHS CPU运行时对照

2026-10-24，仅在开发机测量。测量时原型引擎为OpenVINO，ONNX Runtime安装在`/tmp/qq-runtime-comparison`隔离环境。此后用户已确认采用ORT单线程，原型代码和nsfw依赖已切换；容器尚未部署。本页保留切换前的对照结果。

## 条件

- Intel Xeon Gold 6330 @2.00GHz，112个逻辑CPU可用；Python3.13.2、NumPy2.5.4、Pillow12.3.0。
- OpenVINO2026.4.1、ONNX Runtime1.31.0，CPU运行，无GPU或量化。
- 同一`mobilenetv3_sce_dist/model.onnx`，SHA256 `31814ba076d65d129b89322a767d55d0669c54015134c117da3cf2717defde4e`。
- 两边固定输入`1×3×384×384`、float32，复用优化后的解码/预处理和概率校验。
- OpenVINO使用原型的实际引擎：1 stream、LATENCY、1或2线程，实际精度提示float32。
- ORT使用CPUExecutionProvider、全图优化、SEQUENTIAL、intra线程1或2、inter线程1，并固定batch/height/width。关闭线程自旋，以评估共享服务器上的低频调用配置。这不是对ORT所有调优组合的搜索。
- 每个配置独立进程，5次预热、每项40次串行调用，共两轮；第一轮OV1→ORT1→OV2→ORT2，第二轮倒序。运行时分别按需导入，ORT进程不导入OpenVINO。
- 纯推理复用张量；完整路径每次重新解码、预处理并推理。不含网络下载、QQ通信和并发请求。以下是两轮均值，不把历史基准混入本轮。

线程限制和关闭自旋的取舍参考[ORT线程文档](https://onnxruntime.ai/docs/performance/tune-performance/threading.html)，图优化参考[官方说明](https://onnxruntime.ai/docs/performance/model-optimizations/graph-optimizations.html)。OpenVINO沿用生产原型配置；两套运行时内部调度策略不完全相同。

## 结果

| 运行时/线程 | 512 RGB PNG纯推理 | 512 RGB PNG完整处理 | 1600×1200 JPEG完整处理 | 1600×1200 RGBA PNG完整处理 |
| --- | --- | --- | --- | --- |
| OpenVINO 1 | 19.23ms | 25.87ms | 34.88ms | 83.21ms |
| ORT 1 | 17.02ms | 24.09ms | 35.46ms | 82.42ms |
| OpenVINO 2 | 11.58ms | 21.43ms | 34.07ms | 84.58ms |
| ORT 2 | 10.83ms | 27.50ms | 40.21ms | 92.08ms |

三种计时样本均为非敏感的坐标渐变图；RGBA的alpha固定128。两边单线程速度接近；在本配置下，ORT双线程的纯推理加速没有转化为完整图片处理加速。大透明图仍主要受图片处理影响。共享开发机的尾延迟波动明显，例如单线程透明PNG的单轮P95在84–122ms之间，不据此承诺VPS吞吐或尾延迟。

| 配置 | 模型读取/初始化，不含运行时导入 | 模型初始化后RSS | 全部样本处理后RSS |
| --- | --- | --- | --- |
| OpenVINO 1 | 343ms | 160.9MiB | 212.5MiB |
| ORT 1 | 68ms | 119.0MiB | 174.2MiB |
| OpenVINO 2 | 372ms | 160.0MiB | 211.7MiB |
| ORT 2 | 73ms | 116.9MiB | 169.0MiB |

RSS来自`/proc/self/status`，是整个基准进程的内存，包括Python、运行时、图片和数组分配；不是模型权重大小，也不是NoneBot容器总内存。图片生成和内存分配器的保留会影响最终RSS。运行时导入单独记录在原始JSON中；模型初始化也不等于完整进程启动时间。

三种计时图片，加全黑/中灰/全白和5个固定种子的随机张量，共11个输入，在全部8个进程配置下最高分类一致。跨运行时/线程/轮次最大概率绝对差为`4.7684e-5`，约0.0048个百分点。这只是数值一致性检查，不是准确率或真实群图片评测。

## 判断

目前的低频手动识别场景，ORT单线程值得作为后续替换候选：速度接近，初始化更快，本轮进程RSS少约38MiB。若偏重双线程完整处理延迟，本轮OpenVINO占优。保持单线程仍有利于限制共享服务器上的CPU消耗；增加线程并不保证整条图片链路更快。

基于上述结果，用户随后选择ORT单线程；原型依赖和推理实现已更新，没有增加双后端接口。OpenVINO仅保留在独立比较脚本中。容器构建及VPS部署尚未执行，本机结果不能直接推广到VPS微架构和负载。

## 复现

```bash
uv venv /tmp/qq-runtime-comparison --python .venv/bin/python
uv pip install --python /tmp/qq-runtime-comparison/bin/python \
  numpy==2.5.4 pillow==12.3.0 openvino==2026.4.1 onnxruntime==1.31.0

/tmp/qq-runtime-comparison/bin/python ops/compare_deepghs_runtimes.py \
  --backend openvino --threads 1 --iterations 40 --warmup 5 --output /tmp/ov1.json
/tmp/qq-runtime-comparison/bin/python ops/compare_deepghs_runtimes.py \
  --backend onnxruntime --threads 1 --iterations 40 --warmup 5 --output /tmp/ort1.json
```

两个命令分别启动独立进程。完整对照还需将threads改为2执行，并按上述顺序完成两轮。脚本只加载指定运行时，不修改机器人配置。

原始记录：

- OpenVINO 1线程：[第一轮](benchmarks/2026-10-24-openvino-t1-r1.json)、[第二轮](benchmarks/2026-10-24-openvino-t1-r2.json)
- ORT 1线程：[第一轮](benchmarks/2026-10-24-onnxruntime-t1-r1.json)、[第二轮](benchmarks/2026-10-24-onnxruntime-t1-r2.json)
- OpenVINO 2线程：[第一轮](benchmarks/2026-10-24-openvino-t2-r1.json)、[第二轮](benchmarks/2026-10-24-openvino-t2-r2.json)
- ORT 2线程：[第一轮](benchmarks/2026-10-24-onnxruntime-t2-r1.json)、[第二轮](benchmarks/2026-10-24-onnxruntime-t2-r2.json)
