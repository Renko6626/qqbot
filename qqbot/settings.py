import json
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from .catalog import CATALOG

GroupId = Annotated[str, StringConstraints(pattern=r"^[1-9][0-9]{0,19}$")]


class PluginSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    load_on_start: bool = True
    enabled: bool = False
    group_ids: list[GroupId] = Field(default_factory=list, max_length=500)
    allow_private: bool = False
    options: dict = Field(default_factory=dict)


class SettingsFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plugins: dict[str, PluginSettings] = Field(default_factory=dict)


class PluginStore:
    def __init__(self, path: Path):
        self.path = path
        self._settings = {key: self._normalize(key, PluginSettings()) for key in CATALOG}
        if path.exists():
            saved = SettingsFile.model_validate_json(path.read_text(encoding="utf-8"))
            for key, value in saved.plugins.items():
                if key not in CATALOG:
                    raise ValueError(f"配置包含尚未提供的插件：{key}")
                self._settings[key] = self._normalize(key, value)

    def _normalize(self, plugin_id: str, settings: PluginSettings) -> PluginSettings:
        options = CATALOG[plugin_id].options_model.model_validate(settings.options)
        return settings.model_copy(update={
            "group_ids": list(dict.fromkeys(settings.group_ids)),
            "options": options.model_dump(),
        }, deep=True)

    def get(self, plugin_id: str) -> PluginSettings:
        return self._settings[plugin_id].model_copy(deep=True)

    def save(self, plugin_id: str, settings: PluginSettings) -> PluginSettings:
        value = self._normalize(plugin_id, settings)
        updated = {**self._settings, plugin_id: value}
        content = SettingsFile(plugins=updated).model_dump_json(indent=2)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(content + "\n", encoding="utf-8")
        self._settings = updated
        return self.get(plugin_id)
