from qqbot.image_rating.options import ImageLimits
from qqbot.plugin_api import PluginSpec


SPEC = PluginSpec("anime_rating", "手动图片识别（DeepGHS）",
                  "手动查看动漫图片的 safe / r15 / r18 预测；动图仅分析首帧。",
                  ("/色图识别", "/识别色图"), ImageLimits)
