"""Shared input limits, safe to import during plugin discovery."""
from pydantic import Field

from qqbot.plugin_api import PluginOptions


class ImageLimits(PluginOptions):
    max_download_mb: int = Field(default=10, ge=1, le=20, title="图片大小上限（MiB）")
    max_pixels: int = Field(default=4_000_000, ge=1, le=8_000_000, title="图片像素上限")
