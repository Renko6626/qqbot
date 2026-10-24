from pydantic import Field

from qqbot.albums import AlbumId
from qqbot.image_rating.options import ImageLimits
from qqbot.plugin_api import PluginSpec


class Options(ImageLimits):
    album: AlbumId = Field(default="anime-rating-hits", title="保存图集",
                           description="命中图片写入此图集，首次写入时自动创建。")
    gate_threshold: float = Field(default=0.9, ge=0, le=1, title="二维闸门阈值（动画＋漫画＋插画）")
    threshold: float = Field(default=0.8, ge=0, le=1, title="命中阈值（r15 + r18）")
    reply_text: str = Field(default="我吃！", max_length=500, title="命中回复（留空则仅保存）")


SPEC = PluginSpec("anime_rating_watch", "自动图片监测（DeepGHS）",
                  "仅检查白名单群的二维图片，跳过3D及其他内容；命中后保存并回复，回复留空则仅保存。",
                  (), Options)
