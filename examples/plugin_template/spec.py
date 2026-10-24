from pydantic import Field

from qqbot.plugin_api import PluginOptions, PluginSpec


class Options(PluginOptions):
    reply_text: str = Field(default="你好", min_length=1, max_length=200, title="回复内容")


# Rename both the directory and this ID when copying into qqbot/plugins/.
SPEC = PluginSpec("plugin_template", "示例插件", "回复一段可配置的文字。", ("/示例",), Options)
