"""Shared image analysis; no NoneBot matchers or plugin registration."""
from dataclasses import dataclass, replace
from functools import lru_cache
import os
from time import perf_counter

import anyio
import httpx

from .engine import DeepGHSEngine, GATE_LABELS, InvalidImage, RatingResult, _rgb_tensor, decode_image

TWO_D_LABELS = ("bangumi", "comic", "illustration")


def two_d_score(result: RatingResult) -> float:
    return sum(result.scores[label] for label in TWO_D_LABELS)


class GateRejected(Exception):
    def __init__(self, result: RatingResult):
        super().__init__("未通过二维图片闸门")
        self.result = result


@dataclass(frozen=True)
class ImageAnalysis:
    data: bytes
    result: RatingResult
    gate: RatingResult | None = None


@lru_cache(maxsize=1)
def get_engine() -> DeepGHSEngine:
    return DeepGHSEngine(os.environ.get("BOT_DEEPGHS_MODEL_PATH",
                                        "data/models/deepghs_rating/model.onnx"),
                         threads=int(os.environ.get("BOT_DEEPGHS_THREADS", "1")))


@lru_cache(maxsize=1)
def get_gate_engine() -> DeepGHSEngine:
    return DeepGHSEngine(os.environ.get("BOT_DEEPGHS_GATE_MODEL_PATH",
                                        "data/models/deepghs_gate/model.onnx"),
                         threads=int(os.environ.get("BOT_DEEPGHS_THREADS", "1")), labels=GATE_LABELS)


async def download_image(url: str, max_bytes: int) -> bytes:
    parsed = httpx.URL(url)
    if parsed.scheme not in {"http", "https"} or not parsed.host:
        raise InvalidImage("图片地址无效，请重新发送。")
    async with httpx.AsyncClient(timeout=20) as client:
        async with client.stream("GET", parsed) as response:
            response.raise_for_status()
            data = bytearray()
            async for chunk in response.aiter_bytes():
                if len(data) + len(chunk) > max_bytes:
                    raise InvalidImage("图片文件过大，请发送较小的图片。")
                data.extend(chunk)
    return bytes(data)


async def analyze_image(url: str, *, max_download_mb: int, max_pixels: int,
                        gate_threshold: float | None = None) -> ImageAnalysis:
    data = await download_image(url, max_download_mb * 1024 * 1024)
    engine = get_engine()
    gate_engine = get_gate_engine() if gate_threshold is not None else None

    def analyze():
        if gate_engine is None:
            return ImageAnalysis(data, engine.classify(data, max_pixels=max_pixels))
        started = perf_counter()
        image, first_only = decode_image(data, max_pixels, size=384)
        tensor = _rgb_tensor(image)
        gate = gate_engine.classify_tensor(tensor, first_frame_only=first_only)
        if gate.label not in TWO_D_LABELS or two_d_score(gate) < gate_threshold:
            raise GateRejected(gate)
        rating = engine.classify_tensor(tensor, first_frame_only=first_only)
        rating = replace(rating, total_ms=(perf_counter() - started) * 1000,
                         load_ms=gate.load_ms + rating.load_ms)
        return ImageAnalysis(data, rating, gate)

    return await anyio.to_thread.run_sync(analyze)
