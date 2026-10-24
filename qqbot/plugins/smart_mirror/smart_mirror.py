import anyio
import httpx
from nonebot import on_command
from nonebot.adapters.onebot.v11 import Message, MessageEvent, MessageSegment
from nonebot.matcher import Matcher
from nonebot.params import Arg, CommandArg, Depends
from nonebot.plugin import PluginMetadata

from qqbot.context import PluginContext, plugin_context

from .core import ImageProcessingError, process_image
from .spec import SPEC, Options

__plugin_meta__ = PluginMetadata(
    name=SPEC.name,
    description=SPEC.description,
    usage="/智能左右对称 [图片]，也可回复图片或按提示发送图片。",
)

matcher = on_command("智能左右对称", priority=10, block=True)


def first_image(message: Message) -> MessageSegment | None:
    return next((segment for segment in message if segment.type == "image"), None)


async def download_image(url: str, options: Options) -> bytes:
    parsed = httpx.URL(url)
    if parsed.scheme not in {"http", "https"} or not parsed.host:
        raise ImageProcessingError("图片地址无效，请重新发送图片。")
    limit = options.max_download_mb * 1024 * 1024
    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        async with client.stream("GET", parsed) as response:
            response.raise_for_status()
            chunks = bytearray()
            async for chunk in response.aiter_bytes():
                if len(chunks) + len(chunk) > limit:
                    raise ImageProcessingError("图片文件过大，请发送较小的图片。")
                chunks.extend(chunk)
    return bytes(chunks)


@matcher.handle()
async def select_image(
    matcher: Matcher,
    event: MessageEvent,
    args: Message = CommandArg(),
):
    image = first_image(args)
    if image is None and event.reply:
        image = first_image(event.reply.message)
    if image is not None:
        matcher.set_arg("image", Message(image))


@matcher.got("image", prompt="请发送需要处理的图片。")
async def handle_image(
    matcher: Matcher,
    received: Message = Arg("image"),
    context: PluginContext = Depends(plugin_context, use_cache=False),
):
    image = first_image(received)
    if image is None:
        await matcher.reject("请发送一张图片。")
        return
    url = image.data.get("url")
    if not isinstance(url, str) or not url:
        await matcher.finish("无法获取图片，请重新发送图片。")
        return
    try:
        data = await download_image(url, context.options)
        output = await anyio.to_thread.run_sync(process_image, data, context.options)
    except ImageProcessingError as exc:
        context.logger.warning("图片处理未完成：{}", type(exc).__name__)
        await matcher.finish(str(exc))
        return
    except (httpx.HTTPError, httpx.InvalidURL):
        context.logger.warning("图片下载失败")
        await matcher.finish("图片下载失败，请重新发送或稍后重试。")
        return
    except Exception as exc:
        context.logger.error("图片处理失败：{}", type(exc).__name__)
        await matcher.finish("图片处理失败，请稍后重试。")
        return
    context.logger.info("图片处理完成")
    await matcher.finish(MessageSegment.image(output))
