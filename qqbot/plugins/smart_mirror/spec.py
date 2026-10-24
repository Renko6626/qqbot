from pydantic import Field

from qqbot.plugin_api import PluginOptions, PluginSpec


class Options(PluginOptions):
    max_frames: int = Field(default=60, ge=1, le=60, title="最多处理帧数")
    max_download_mb: int = Field(default=10, ge=1, le=20, title="图片大小上限（MiB）")
    max_pixels: int = Field(
        default=4_000_000, ge=1, le=8_000_000, title="单帧像素上限"
    )


SPEC = PluginSpec(
    "smart_mirror",
    "智能左右对称",
    "以最大人脸为轴，将左侧镜像到右侧；未检测到人脸时使用图片中线。支持静态图和 GIF。",
    ("/智能左右对称",),
    Options,
)
