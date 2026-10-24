from io import BytesIO
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from qqbot.image_rating.engine import (
    DeepGHSEngine, InferenceUnavailable, InvalidImage, decode_image, preprocess, probability_scores,
)


def png(color="red"):
    b = BytesIO(); Image.new("RGB", (16, 16), color).save(b, format="PNG")
    return b.getvalue()


def test_preprocess_matches_upstream_half_normalization_and_white_alpha():
    tensor = preprocess(Image.new("RGB", (10, 20), "red"))
    assert tensor.shape == (1, 3, 384, 384) and tensor.dtype == np.float32
    assert tensor[0, :, 0, 0].tolist() == [1.0, -1.0, -1.0]
    transparent = preprocess(Image.new("RGBA", (2, 2), (0, 0, 0, 0)))
    assert transparent[0, :, 0, 0].tolist() == [1.0, 1.0, 1.0]


def test_probability_output_is_not_softmaxed_twice():
    scores = probability_scores(np.array([[0.99, 0.005, 0.005]], dtype=np.float32))
    assert scores["safe"] == pytest.approx(0.99)
    assert scores["r18"] == pytest.approx(0.005)
    with pytest.raises(InferenceUnavailable):
        probability_scores(np.array([[4.0, 0.1, 0.2]]))


def test_prepared_decode_applies_exif_before_resizing():
    image = Image.new("RGB", (2, 4), "blue")
    image.paste("red", (0, 0, 2, 2))
    exif = Image.Exif(); exif[274] = 6  # Rotate clockwise: blue left, red right.
    encoded = BytesIO(); image.save(encoded, format="PNG", exif=exif)
    prepared, first_only = decode_image(encoded.getvalue(), max_pixels=8, size=8)
    assert prepared.size == (8, 8) and prepared.mode == "RGB" and not first_only
    assert prepared.getpixel((0, 0)) == (0, 0, 255)
    assert prepared.getpixel((7, 0)) == (255, 0, 0)
    assert 274 not in prepared.getexif()


def test_rgb_transparent_color_key_keeps_white_background():
    encoded = BytesIO()
    Image.new("RGB", (2, 2), "red").save(encoded, format="PNG", transparency=(255, 0, 0))
    original, _ = decode_image(encoded.getvalue(), max_pixels=4)
    prepared, _ = decode_image(encoded.getvalue(), max_pixels=4, size=8)
    assert prepared.getpixel((0, 0)) == (255, 255, 255)
    assert preprocess(original)[0, :, 0, 0].tolist() == [1.0, 1.0, 1.0]


def test_image_limits_and_animated_first_frame_are_explicit():
    with pytest.raises(InvalidImage): decode_image(png(), max_pixels=1)
    with pytest.raises(InvalidImage): decode_image(b"not an image", max_pixels=100)
    b = BytesIO(); Image.new("RGB", (2, 2), "red").save(
        b, format="GIF", save_all=True, append_images=[Image.new("RGB", (2, 2), "blue")], duration=100)
    image, first_only = decode_image(b.getvalue(), max_pixels=10)
    assert first_only and image.convert("RGB").getpixel((0, 0)) == (255, 0, 0)


def test_missing_model_has_actionable_error(tmp_path):
    with pytest.raises(InferenceUnavailable, match="模型未配置"):
        DeepGHSEngine(tmp_path / "missing.onnx").classify(png())


def test_real_ort_engine_reuses_loaded_model_and_preserves_probabilities():
    pytest.importorskip("onnxruntime")
    path = Path(__file__).parent / "fixtures" / "rating_channel_means.onnx"
    engine = DeepGHSEngine(path)
    first = engine.classify(png())
    second = engine.classify(png())
    assert first.label == "safe" and 0.78 < first.scores["safe"] < 0.80
    assert first.scores == second.scores
    assert first.load_ms > 0 and second.load_ms == 0
    assert not first.first_frame_only
