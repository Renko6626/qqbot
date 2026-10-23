from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field


class NoOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PingOptions(NoOptions):
    reply_text: str = Field(default="连接正常", min_length=1, max_length=200,
                            title="连接检查回复")


@dataclass(frozen=True)
class PluginSpec:
    id: str
    name: str
    description: str
    commands: tuple[str, ...]
    options_model: type[BaseModel] = NoOptions

    @property
    def module(self) -> str:
        return f"qqbot.plugins.{self.id}"


CATALOG = {
    spec.id: spec for spec in (
        PluginSpec("ping", "连接检查", "检查 QQ 消息与机器人之间的连接。",
                   ("/测试连接",), PingOptions),
        PluginSpec("help", "帮助", "列出当前会话可以使用的插件和指令。",
                   ("/帮助",)),
    )
}
