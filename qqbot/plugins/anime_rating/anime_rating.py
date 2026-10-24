import httpx
from nonebot import on_command
from nonebot.adapters.onebot.v11 import Message, MessageEvent
from nonebot.matcher import Matcher
from nonebot.params import Arg, CommandArg, Depends
from nonebot.plugin import PluginMetadata

from qqbot.context import PluginContext, plugin_context
from qqbot.image_rating.engine import InferenceUnavailable, InvalidImage, RatingResult
from qqbot.image_rating import service
from .spec import SPEC

__plugin_meta__ = PluginMetadata(name=SPEC.name, description=SPEC.description,
                                usage="/色图识别 附图、回复图片，或按提示补图。")
matcher = on_command("色图识别", aliases={"识别色图"}, priority=10, block=True)


def first_image(message: Message):
    return next((s for s in message if s.type == "image"), None)


def report(result: RatingResult) -> str:
    lines = [f"DeepGHS 动漫图片分级：{result.label}"]
    lines.extend(f"{label}：{score:.1%}" for label, score in result.scores.items())
    lines.append(f"模型推理 {result.inference_ms:.1f}ms，图片处理总计 {result.total_ms:.1f}ms（不含下载）")
    if result.load_ms:
        lines.append(f"本次包含首次加载 {result.load_ms:.0f}ms")
    if result.first_frame_only:
        lines.append("动图仅分析首帧，结果不代表全部帧。")
    lines.append("模型分级仅供参考，不代表人工审核结论。")
    return "\n".join(lines)


@matcher.handle()
async def select_image(matcher: Matcher, event: MessageEvent, args: Message = CommandArg()):
    image = first_image(args)
    if image is None and event.reply:
        image = first_image(event.reply.message)
    if image is not None:
        matcher.set_arg("image", Message(image))


@matcher.got("image", prompt="请发送需要识别的图片。")
async def identify(matcher: Matcher, received: Message = Arg("image"),
                   context: PluginContext = Depends(plugin_context, use_cache=False)):
    image = first_image(received)
    if image is None:
        await matcher.reject("请发送一张图片。")
        return
    url = image.data.get("url")
    if not isinstance(url, str) or not url:
        await matcher.finish("无法获取图片，请重新发送。")
        return
    try:
        analysis = await service.analyze_image(url, max_download_mb=context.options.max_download_mb,
                                               max_pixels=context.options.max_pixels)
        result = analysis.result
    except (InvalidImage, InferenceUnavailable) as exc:
        context.logger.warning("识别未完成：{}", type(exc).__name__)
        await matcher.finish(str(exc))
        return
    except (httpx.HTTPError, httpx.InvalidURL):
        context.logger.warning("图片下载失败")
        await matcher.finish("图片下载失败，请重新发送或稍后重试。")
        return
    except Exception as exc:
        context.logger.error("识别失败：{}", type(exc).__name__)
        await matcher.finish("识别失败，请联系管理员检查模型配置。")
        return
    context.logger.info("手动识别完成 label={} inference_ms={:.1f}", result.label, result.inference_ms)
    await matcher.finish(report(result))
