from pydantic import Field

from qqbot.plugin_api import PluginOptions, PluginSpec


class Options(PluginOptions):
    reply_text: str = Field(default="连接正常", min_length=1, max_length=200,
                            title="连接检查回复")


SPEC = PluginSpec("ping", "连接检查", "检查 QQ 消息与机器人之间的连接。",
                  ("/测试连接",), Options)
