"""The legacy left-side mirror algorithm, with bounded image decoding."""

import io
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from .spec import Options


MAX_TOTAL_PIXELS = 64_000_000


class ImageProcessingError(ValueError):
    """A safe, user-facing explanation of an unsupported image."""


def load_classifiers() -> list[cv2.CascadeClassifier]:
    paths = (
        Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml",
        Path(__file__).parent / "models" / "lbpcascade_animeface.xml",
    )
    classifiers = [cv2.CascadeClassifier(str(path)) for path in paths]
    if any(classifier.empty() for classifier in classifiers):
        raise RuntimeError("Face detection model unavailable")
    return classifiers


def get_face_center_x(
    image: Image.Image, classifiers: list[cv2.CascadeClassifier]
) -> int:
    gray = cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2GRAY)
    for classifier in classifiers:
        faces = classifier.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
        )
        if len(faces):
            x, _, width, _ = max(faces, key=lambda face: face[2] * face[3])
            return int(x + width / 2)
    return -1


def mirror_frame(frame: Image.Image, center_x: int) -> Image.Image:
    # Preserve the original crop-to-axis behavior, including odd-width crops.
    # A one-pixel image has no left half, so duplicate its sole column.
    axis = max(1, min(frame.width, center_x if center_x >= 0 else frame.width // 2))
    left = frame.crop((0, 0, axis, frame.height))
    result = Image.new("RGBA", (axis * 2, frame.height))
    result.paste(left, (0, 0))
    result.paste(ImageOps.mirror(left), (axis, 0))
    return result


def _gif_palette(frame: Image.Image) -> Image.Image:
    # Reserve index 255 explicitly: adaptive RGBA quantization can assign an
    # opaque color to that index, making it disappear when marked transparent.
    palette = frame.convert("RGB").quantize(colors=255, dither=Image.Dither.NONE)
    palette.putpalette((palette.getpalette() or [])[:765] + [0, 0, 0])
    transparent = frame.getchannel("A").point(lambda value: 255 if value < 128 else 0)
    palette.paste(255, mask=transparent)
    palette.info["transparency"] = 255
    return palette


def process_image(data: bytes, options: Options) -> bytes:
    """Decode, detect, mirror and encode entirely inside the caller's worker thread."""
    if len(data) > options.max_download_mb * 1024 * 1024:
        raise ImageProcessingError("图片文件过大，请发送较小的图片。")
    frames: list[Image.Image] = []
    durations: list[int] = []
    classifiers = load_classifiers()
    try:
        with Image.open(io.BytesIO(data)) as source:
            if source.width * source.height > options.max_pixels:
                raise ImageProcessingError("图片像素过多，请缩小后重试。")
            count = getattr(source, "n_frames", 1)
            if count > options.max_frames:
                raise ImageProcessingError("图片帧数过多，请使用较短的动图。")
            if source.width * source.height * count > MAX_TOTAL_PIXELS:
                raise ImageProcessingError("动图总像素过多，请缩小或减少帧数后重试。")
            loop_options = {"loop": source.info["loop"]} if "loop" in source.info else {}
            for index in range(count):
                source.seek(index)
                if source.width * source.height > options.max_pixels:
                    raise ImageProcessingError("图片像素过多，请缩小后重试。")
                # Pillow applies GIF disposal/compositing while seeking frames.
                frame = source.convert("RGBA")
                frames.append(mirror_frame(frame, get_face_center_x(frame, classifiers)))
                durations.append(source.info.get("duration", 100))
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ImageProcessingError("无法读取这张图片，请发送有效的静态图片或 GIF。") from exc

    size = (max(frame.width for frame in frames), max(frame.height for frame in frames))
    normalized = []
    for frame in frames:
        if frame.size == size:
            normalized.append(frame)
            continue
        canvas = Image.new("RGBA", size)
        canvas.paste(frame, ((size[0] - frame.width) // 2, (size[1] - frame.height) // 2))
        normalized.append(canvas)
    output = io.BytesIO()
    if len(normalized) == 1:
        normalized[0].save(output, format="PNG")
    else:
        palettes = [_gif_palette(frame) for frame in normalized]
        palettes[0].save(
            output,
            format="GIF",
            save_all=True,
            append_images=palettes[1:],
            duration=durations,
            **loop_options,
            disposal=2,
            transparency=255,
            optimize=False,
        )
    return output.getvalue()
