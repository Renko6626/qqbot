import io

import pytest
from PIL import Image

from qqbot.plugins.smart_mirror.core import (
    ImageProcessingError,
    get_face_center_x,
    load_classifiers,
    mirror_frame,
    process_image,
)
from qqbot.plugins.smart_mirror.spec import Options


def encode(image, **kwargs):
    output = io.BytesIO()
    image.save(output, **kwargs)
    return output.getvalue()


def test_static_no_face_crops_left_then_mirrors_with_alpha():
    image = Image.new("RGBA", (5, 1))
    image.putdata([
        (255, 0, 0, 80), (0, 255, 0, 255), (0, 0, 255, 255),
        (1, 2, 3, 255), (1, 2, 3, 255),
    ])
    output = Image.open(io.BytesIO(process_image(encode(image, format="PNG"), Options())))
    assert output.format == "PNG"
    assert output.size == (4, 1)
    assert [output.getpixel((x, 0)) for x in range(output.width)] == [
        (255, 0, 0, 80), (0, 255, 0, 255),
        (0, 255, 0, 255), (255, 0, 0, 80),
    ]


def test_explicit_face_axis_and_single_pixel():
    image = Image.new("RGBA", (7, 1))
    image.putdata([(value, 0, 0, 255) for value in range(7)])
    mirrored = mirror_frame(image, 3)
    assert mirrored.size == (6, 1)
    assert [mirrored.getpixel((x, 0))[0] for x in range(6)] == [0, 1, 2, 2, 1, 0]
    tiny = mirror_frame(image.crop((0, 0, 1, 1)), -1)
    assert [tiny.getpixel((x, 0)) for x in range(tiny.width)] == [
        (0, 0, 0, 255), (0, 0, 0, 255)
    ]


def test_gif_preserves_duration_transparency_and_normalizes_axes(monkeypatch):
    first = Image.new("RGBA", (6, 2))
    second = first.copy()
    first.putpixel((1, 0), (255, 0, 0, 255))
    second.putpixel((1, 0), (0, 255, 0, 255))
    data = encode(
        first, format="GIF", save_all=True, append_images=[second],
        duration=[70, 130], disposal=2, loop=2,
    )
    axes = iter([2, 3])
    monkeypatch.setattr(
        "qqbot.plugins.smart_mirror.core.get_face_center_x", lambda *_: next(axes)
    )
    output = Image.open(io.BytesIO(process_image(data, Options())))
    assert output.format == "GIF"
    assert output.n_frames == 2
    assert output.info["loop"] == 2
    assert output.size == (6, 2)
    for index, duration in enumerate([70, 130]):
        output.seek(index)
        assert output.info["duration"] == duration
        rgba = output.convert("RGBA")
        assert rgba.getpixel((0, 1))[3] == 0
        assert rgba.getpixel((2 if index == 0 else 1, 0)) == (
            (255, 0, 0, 255) if index == 0 else (0, 255, 0, 255)
        )


def test_size_and_frame_limits():
    image = Image.new("RGB", (4, 4), "red")
    with pytest.raises(ImageProcessingError, match="像素"):
        process_image(encode(image, format="PNG"), Options(max_pixels=15))
    data = encode(
        image, format="GIF", save_all=True,
        append_images=[Image.new("RGB", (4, 4), "blue")], duration=100,
    )
    with pytest.raises(ImageProcessingError, match="帧数"):
        process_image(data, Options(max_frames=1))
    with pytest.raises(ImageProcessingError, match="文件过大"):
        process_image(b"x" * (1024 * 1024 + 1), Options(max_download_mb=1))


def test_both_face_detectors_load_and_accept_real_image():
    classifiers = load_classifiers()
    assert len(classifiers) == 2
    assert get_face_center_x(Image.new("RGB", (64, 64), "white"), classifiers) == -1


def test_gif_aggregate_pixel_limit_and_absent_loop(monkeypatch):
    data = encode(
        Image.new("RGB", (4, 4), "red"), format="GIF", save_all=True,
        append_images=[Image.new("RGB", (4, 4), "blue")], duration=100,
    )
    output = Image.open(io.BytesIO(process_image(data, Options())))
    assert output.n_frames == 2
    assert "loop" not in output.info
    monkeypatch.setattr("qqbot.plugins.smart_mirror.core.MAX_TOTAL_PIXELS", 31)
    with pytest.raises(ImageProcessingError, match="动图总像素过多"):
        process_image(data, Options())
