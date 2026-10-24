import os
from pathlib import Path

import anyio
import httpx
from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageEvent, MessageSegment
from nonebot.params import Depends
from nonebot.plugin import PluginMetadata

from qqbot.context import PluginContext, plugin_context
from qqbot.image_rating import service
from qqbot.image_rating.engine import InferenceUnavailable, InvalidImage
from .archive import save_hit
from .spec import SPEC

__plugin_meta__ = PluginMetadata(name=SPEC.name, description=SPEC.description,
                                usage="在管理页启用并配置群白名单、阈值和回复文案。")


def is_monitor_message(event: MessageEvent) -> bool:
    if not isinstance(event, GroupMessageEvent) or event.user_id == event.self_id:
        return False
    text = event.get_plaintext().lstrip().split(maxsplit=1)
    if text and text[0] in {"/色图识别", "/识别色图"}:
        return False
    return any(segment.type == "image" for segment in event.message)


matcher = on_message(rule=is_monitor_message, priority=20, block=False)
REACTION_IMAGE = Path(__file__).with_name("assets") / "milly_cat.jpg"


@matcher.handle()
async def monitor(bot: Bot, event: GroupMessageEvent,
                  context: PluginContext = Depends(plugin_context, use_cache=False)):
    options = context.options
    saved = 0
    for image in event.message:
        if image.type != "image":
            continue
        url = image.data.get("url")
        if not isinstance(url, str) or not url:
            context.logger.warning("自动识别跳过：图片地址缺失")
            continue
        try:
            analysis = await service.analyze_image(url, max_download_mb=options.max_download_mb,
                                                   max_pixels=options.max_pixels,
                                                   gate_threshold=options.gate_threshold)
            score = analysis.result.scores["r15"] + analysis.result.scores["r18"]
            if score < options.threshold:
                context.logger.info("自动识别未命中 score={:.4f} threshold={:.4f}", score, options.threshold)
                continue
            await anyio.to_thread.run_sync(lambda: save_hit(
                analysis, Path(os.environ.get("BOT_DEEPGHS_ARCHIVE_DIR", "data/anime_rating_hits")),
                group_id=event.group_id, message_id=event.message_id))
            saved += 1
            context.logger.info("自动识别已保存 score={:.4f} threshold={:.4f} inference_ms={:.1f}",
                                score, options.threshold, analysis.result.inference_ms)
        except service.GateRejected as exc:
            context.logger.info("二维闸门跳过 label={} score={:.4f} threshold={:.4f}",
                                exc.result.label, service.two_d_score(exc.result), options.gate_threshold)
        except (InvalidImage, InferenceUnavailable, httpx.HTTPError, httpx.InvalidURL) as exc:
            context.logger.warning("自动识别跳过：{}", type(exc).__name__)
        except Exception as exc:
            context.logger.error("自动识别或保存失败：{}", type(exc).__name__)
    if saved and options.reply_text:
        await bot.send(event, MessageSegment.reply(event.message_id)
                       + MessageSegment.text(options.reply_text)
                       + MessageSegment.image(REACTION_IMAGE.read_bytes()))
