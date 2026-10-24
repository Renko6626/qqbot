from pydantic import Field

from qqbot.image_rating.options import ImageLimits
from qqbot.plugin_api import PluginSpec


class Options(ImageLimits):
    threshold: float = Field(default=0.8, ge=0, le=1, title="命中阈值（r15 + r18）")
    reply_text: str = Field(default="我吃！", max_length=500, title="命中回复（留空则仅保存）")


SPEC = PluginSpec("anime_rating_watch", "自动图片监测（DeepGHS）",
                  "仅检查白名单群的新图片，命中后保存并回复文字和表情包；回复留空则仅保存。",
                  (), Options)
