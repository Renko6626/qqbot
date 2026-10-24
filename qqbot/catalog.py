"""Discover repository plugin declarations without importing their handlers."""
from importlib import import_module
from pathlib import Path

from .plugin_api import PluginOptions, PluginSpec

# Retain the public name used by existing plugin configuration models.
NoOptions = PluginOptions


def discover_plugins() -> dict[str, PluginSpec]:
    catalog = {}
    for directory in sorted((Path(__file__).parent / "plugins").iterdir()):
        if not directory.is_dir() or not (directory / "spec.py").is_file():
            continue
        if not directory.name.isidentifier() or directory.name.startswith("_"):
            continue
        spec = import_module(f"qqbot.plugins.{directory.name}.spec").SPEC
        if not isinstance(spec, PluginSpec) or spec.id != directory.name:
            raise ValueError(f"插件声明 ID 必须与目录名称一致：{directory.name}")
        if not issubclass(spec.options_model, PluginOptions):
            raise ValueError(f"插件参数模型必须继承 PluginOptions：{spec.id}")
        catalog[spec.id] = spec
    return catalog


CATALOG = discover_plugins()
