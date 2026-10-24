from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from .catalog import CATALOG

GroupId = Annotated[str, StringConstraints(pattern=r"^[1-9][0-9]{0,19}$")]
UserId = GroupId


class PluginSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    load_on_start: bool = True
    enabled: bool = False
    group_ids: list[GroupId] = Field(default_factory=list, max_length=500)
    # Absent group entry means every member; an empty entry permits nobody.
    group_user_ids: dict[GroupId, list[UserId]] = Field(default_factory=dict)
    allow_private: bool = False
    # None preserves the original allow_private=True (all private users).
    private_user_ids: list[UserId] | None = Field(default=None, max_length=1000)
    options: dict = Field(default_factory=dict)
    # Sparse per-group overrides; absent fields inherit public options.
    group_options: dict[GroupId, dict] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_group_members(self):
        if self.group_user_ids.keys() - set(self.group_ids):
            raise ValueError("成员白名单必须属于已允许的群")
        if self.group_options.keys() - set(self.group_ids):
            raise ValueError("群参数必须属于已允许的群")
        if any(len(users) > 1000 for users in self.group_user_ids.values()):
            raise ValueError("每群成员白名单最多1000个用户")
        return self


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
        model = CATALOG[plugin_id].options_model
        options = model.model_validate(settings.options)
        group_options = {}
        for group_id, override in settings.group_options.items():
            merged = model.model_validate({**options.model_dump(), **override}).model_dump()
            # Validate the complete result but retain only explicit keys.
            group_options[group_id] = {key: merged[key] for key in override}
        return settings.model_copy(update={
            "group_ids": list(dict.fromkeys(settings.group_ids)),
            "group_user_ids": {group: list(dict.fromkeys(users))
                               for group, users in settings.group_user_ids.items()},
            "private_user_ids": (list(dict.fromkeys(settings.private_user_ids))
                                 if settings.private_user_ids is not None else None),
            "options": options.model_dump(),
            "group_options": group_options,
        }, deep=True)

    def resolve_options(self, plugin_id: str, group_id: str | None = None) -> BaseModel:
        settings = self._settings[plugin_id]
        override = settings.group_options.get(group_id, {}) if group_id is not None else {}
        return CATALOG[plugin_id].options_model.model_validate({**settings.options, **override})

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
