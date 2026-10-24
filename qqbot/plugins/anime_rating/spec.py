from pydantic import Field

from qqbot.plugin_api import PluginOptions, PluginSpec


class Options(PluginOptions):
    max_download_mb: int = Field(default=10, ge=1, le=20, title="图片大小上限（MiB）")
    max_pixels: int = Field(default=4_000_000, ge=1, le=8_000_000, title="图片像素上限")


SPEC = PluginSpec("anime_rating", "图片分级（DeepGHS）",
                  "手动查看动漫图片的 safe / r15 / r18 预测；动图仅分析首帧。",
                  ("/色图识别", "/识别色图"), Options)
