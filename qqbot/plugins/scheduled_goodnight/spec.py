from pydantic import Field

from qqbot.albums import AlbumId
from qqbot.plugin_api import PluginOptions, PluginSpec


class Options(PluginOptions):
    time: str = Field(default="23:00", pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$",
                      title="每天发送时间", description="北京时间，格式为 HH:MM，例如 23:00。")
    text: str = Field(default="晚安，做个好梦。", max_length=2000, title="晚安文案",
                      description="留空则只发图片；没有图片时跳过。")
    album: AlbumId = Field(default="goodnight", title="图片图集",
                           description="从此图集随机选一张图片；图集为空时只发文字。")


SPEC = PluginSpec("scheduled_goodnight", "定时晚安",
                  "每天按北京时间向指定群发送自定义晚安文案和随机图集图片。",
                  (), Options)
