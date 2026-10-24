from pydantic import Field

from qqbot.image_rating.options import ImageLimits
from qqbot.plugin_api import PluginSpec


class Options(ImageLimits):
    threshold: float = Field(default=0.8, ge=0, le=1, title="命中阈值（r15 + r18）")
    reply_text: str = Field(default="", max_length=500, title="命中回复（留空则仅保存）")


SPEC = PluginSpec("anime_rating_watch", "自动图片监测（DeepGHS）",
                  "仅检查白名单群的新图片，r15+r18达到阈值后保存；填写回复文案后回复。",
                  (), Options)
