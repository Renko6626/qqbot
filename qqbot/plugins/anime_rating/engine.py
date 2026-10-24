"""Local DeepGHS anime_rating inference. Importing this module loads no model."""
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from threading import Lock
from time import perf_counter

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

LABELS = ("safe", "r15", "r18")


class InferenceUnavailable(RuntimeError):
    pass


class InvalidImage(ValueError):
    pass


@dataclass(frozen=True)
class RatingResult:
    scores: dict[str, float]
    label: str
    inference_ms: float
    total_ms: float
    load_ms: float
    first_frame_only: bool


def _resize_rgb(image: Image.Image, size: int) -> Image.Image:
    # RGB PNGs may also carry a transparent color key (tRNS).
    if image.mode != "RGB" or "transparency" in image.info:
        rgba = image.convert("RGBA")
        white = Image.new("RGBA", rgba.size, "white")
        white.alpha_composite(rgba)
        image = white.convert("RGB")
    return image.resize((size, size), Image.Resampling.BILINEAR)


def _rgb_tensor(rgb: Image.Image) -> np.ndarray:
    values = np.array(rgb, dtype=np.float32)
    # Keep the upstream operation order without allocating intermediate arrays.
    values /= np.float32(255)
    values -= np.float32(0.5)
    values /= np.float32(0.5)
    return np.ascontiguousarray(values.transpose(2, 0, 1)[None])


def preprocess(image: Image.Image, size: int = 384) -> np.ndarray:
    """Match upstream generic classifier: white RGB, bilinear, CHW, mean/std .5."""
    return _rgb_tensor(_resize_rgb(ImageOps.exif_transpose(image), size))


def decode_image(data: bytes, max_pixels: int, *, size: int | None = None) -> tuple[Image.Image, bool]:
    """Detach the first frame; optionally return oriented, resized white RGB."""
    try:
        with Image.open(BytesIO(data)) as source:
            if source.width * source.height > max_pixels:
                raise InvalidImage("图片像素过多，请缩小后重试。")
            first_only = bool(getattr(source, "is_animated", False))
            if size is not None:
                # Own this image: orient in place and shrink before detaching it.
                # Avoid both the full-resolution copy and exif_transpose's copy.
                ImageOps.exif_transpose(source, in_place=True)
                return _resize_rgb(source, size), first_only
            # Freeze the first frame, preserving EXIF until preprocess handles it.
            return source.copy(), first_only
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise InvalidImage("无法读取图片，请重新发送有效图片。") from exc


def probability_scores(output: np.ndarray) -> dict[str, float]:
    values = np.asarray(output, dtype=np.float32).reshape(-1)
    if values.shape != (3,) or not np.isfinite(values).all():
        raise InferenceUnavailable("模型输出不符合三分类约定。")
    if np.any(values < 0) or np.any(values > 1) or not np.isclose(values.sum(), 1, atol=0.01):
        raise InferenceUnavailable("模型输出不是预期的概率，请核对模型文件。")
    # Official graph already ends in Softmax. Applying it again is incorrect.
    return dict(zip(LABELS, map(float, values)))


class DeepGHSEngine:
    def __init__(self, model_path: str | Path, *, size: int = 384, threads: int = 1):
        if size != 384 or threads not in {1, 2}:
            raise ValueError("原型使用384分辨率与1或2个CPU线程")
        self.model_path = Path(model_path)
        self.size = size
        self.threads = threads
        self._lock = Lock()
        self._compiled = None
        self._request = None
        self._output = None
        self.load_ms = 0.0

    def _load(self) -> None:
        if self._compiled is not None:
            return
        if not self.model_path.is_file():
            raise InferenceUnavailable("识别模型未配置，请联系管理员设置模型文件。")
        if self.model_path.suffix == ".xml" and not self.model_path.with_suffix(".bin").is_file():
            raise InferenceUnavailable("模型权重文件缺失，请核对配置。")
        try:
            import openvino as ov
        except ImportError as exc:
            raise InferenceUnavailable("识别运行时未安装，请安装项目的 nsfw 可选依赖。") from exc
        started = perf_counter()
        core = ov.Core()
        model = core.read_model(str(self.model_path))
        if len(model.inputs) != 1 or len(model.outputs) != 1:
            raise InferenceUnavailable("模型输入输出数量不符合约定。")
        shape = model.input(0).partial_shape
        if shape.rank.is_dynamic or shape.rank.get_length() != 4:
            raise InferenceUnavailable("模型输入必须为NCHW四维张量。")
        if not shape[1].is_dynamic and shape[1].get_length() != 3:
            raise InferenceUnavailable("模型输入通道必须为RGB三通道。")
        model.reshape({model.input(0): [1, 3, self.size, self.size]})
        if model.output(0).shape != [1, 3]:
            raise InferenceUnavailable("模型必须输出 safe / r15 / r18 三项。")
        compiled = core.compile_model(model, "CPU", {
            "INFERENCE_NUM_THREADS": self.threads, "NUM_STREAMS": 1,
            "PERFORMANCE_HINT": "LATENCY",
        })
        self._request = compiled.create_infer_request()
        self._output = compiled.output(0)
        self._compiled = compiled
        self.load_ms = (perf_counter() - started) * 1000

    def load(self) -> float:
        with self._lock:
            self._load()
            return self.load_ms

    def _infer(self, tensor: np.ndarray) -> tuple[dict[str, float], float]:
        started = perf_counter()
        output = self._request.infer({0: tensor})[self._output]
        elapsed = (perf_counter() - started) * 1000
        return probability_scores(output), elapsed

    def infer_tensor(self, tensor: np.ndarray) -> dict[str, float]:
        """Preprocessed-tensor path for isolated CPU benchmarks."""
        with self._lock:
            self._load()
            return self._infer(tensor)[0]

    def classify(self, data: bytes, *, max_pixels: int = 4_000_000) -> RatingResult:
        started = perf_counter()
        image, first_only = decode_image(data, max_pixels, size=self.size)
        tensor = _rgb_tensor(image)
        with self._lock:
            cold = self._compiled is None
            self._load()
            scores, infer_ms = self._infer(tensor)
            load_ms = self.load_ms if cold else 0.0
        return RatingResult(scores, max(scores, key=scores.get), infer_ms,
                            (perf_counter() - started) * 1000, load_ms, first_only)
