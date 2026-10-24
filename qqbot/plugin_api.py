"""Small declaration contract; safe to import without starting NoneBot."""
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict


class PluginOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


@dataclass(frozen=True)
class PluginSpec:
    id: str
    name: str
    description: str
    commands: tuple[str, ...]
    options_model: type[BaseModel] = PluginOptions

    @property
    def module(self) -> str:
        return f"qqbot.plugins.{self.id}.{self.id}"
