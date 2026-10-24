"""Shared image analysis; no NoneBot matchers or plugin registration."""
from dataclasses import dataclass
from functools import lru_cache
import os

import anyio
import httpx

from .engine import DeepGHSEngine, InvalidImage, RatingResult


@dataclass(frozen=True)
class ImageAnalysis:
    data: bytes
    result: RatingResult


@lru_cache(maxsize=1)
def get_engine() -> DeepGHSEngine:
    return DeepGHSEngine(os.environ.get("BOT_DEEPGHS_MODEL_PATH",
                                        "data/models/deepghs_rating/model.onnx"),
                         threads=int(os.environ.get("BOT_DEEPGHS_THREADS", "1")))


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


async def analyze_image(url: str, *, max_download_mb: int, max_pixels: int) -> ImageAnalysis:
    data = await download_image(url, max_download_mb * 1024 * 1024)
    engine = get_engine()
    result = await anyio.to_thread.run_sync(lambda: engine.classify(data, max_pixels=max_pixels))
    return ImageAnalysis(data, result)
