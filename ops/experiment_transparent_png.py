#!/usr/bin/env python3
"""Development-only alpha preprocessing experiment; never selects a bot runtime path."""
import argparse
from io import BytesIO
import json
from pathlib import Path
import platform
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from PIL import Image, ImageDraw, ImageOps, __version__ as pillow_version
from qqbot.image_rating.engine import DeepGHSEngine, _resize_rgb, _rgb_tensor


def paste_white(image, size):
    rgba = image if image.mode == "RGBA" else image.convert("RGBA")
    white = Image.new("RGB", rgba.size, "white")
    white.paste(rgba, mask=rgba)
    return white.resize((size, size), Image.Resampling.BILINEAR)


def resize_first(image, size):
    rgba = image if image.mode == "RGBA" else image.convert("RGBA")
    # Pillow resizes RGBA through premultiplied alpha; still not pixel-equivalent
    # to compositing on white before interpolation and integer rounding.
    small = rgba.resize((size, size), Image.Resampling.BILINEAR)
    white = Image.new("RGBA", small.size, "white")
    white.alpha_composite(small)
    return white.convert("RGB")


METHODS = {"reference": _resize_rgb, "paste_white": paste_white, "resize_first": resize_first}


def verify_white_compositing():
    # Independent channel/alpha combinations over white, including both endpoints.
    color, alpha = np.meshgrid(np.arange(256, dtype="uint8"), np.arange(256, dtype="uint8"))
    image = Image.fromarray(np.stack((color, 255-color, color, alpha), -1))
    np.testing.assert_array_equal(np.array(_resize_rgb(image, 256)), np.array(paste_white(image, 256)))


def samples():
    width, height = 1600, 1200
    y, x = np.indices((height, width))
    rgb = np.stack((x % 256, y % 256, (x + y) % 256), -1).astype("uint8")
    for name, alpha in [
        ("constant_alpha_128", np.full((height, width), 128, dtype="uint8")),
        ("varying_alpha", ((x + y) % 256).astype("uint8")),
        ("checker_alpha", (((x + y) % 2) * 255).astype("uint8")),
        ("low_alpha", ((x % 4) + 1).astype("uint8")),
    ]:
        yield name, Image.fromarray(np.dstack((rgb, alpha))), {}
    # Noisy hidden colors and a hard alpha edge, rather than a uniform backdrop.
    rng = np.random.default_rng(42)
    image = Image.fromarray(rng.integers(0, 256, (height, width, 4), dtype="uint8"))
    alpha = Image.new("L", image.size, 0)
    ImageDraw.Draw(alpha).ellipse((170, 90, 1410, 1100), fill=255)
    image.putalpha(alpha)
    yield "noisy_cutout", image, {}
    palette = Image.fromarray(((x + y) % 256).astype("uint8")).convert("P")
    palette.putpalette([channel for i in range(256) for channel in (i, 255-i, (i*3) % 256)])
    yield "palette_alpha", palette, {"transparency": bytes(range(256))}
    image = Image.new("RGBA", (2000, 2000), (40, 120, 210, 128))
    ImageDraw.Draw(image).rectangle((500, 500, 1499, 1499), fill=(220, 40, 80, 230))
    yield "four_megapixel_shapes", image, {}


def render(data, method):
    with Image.open(BytesIO(data)) as source:
        if source.width * source.height > 4_000_000:
            raise ValueError("experiment input exceeds production pixel limit")
        ImageOps.exif_transpose(source, in_place=True)
        return METHODS[method](source, 384)


def decode_only(data):
    with Image.open(BytesIO(data)) as source:
        source.load()


def average(call, count):
    started = perf_counter()
    for _ in range(count):
        call()
    return (perf_counter() - started) * 1000 / count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=12)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.iterations < 1:
        parser.error("iterations must be positive")
    verify_white_compositing()
    engine = DeepGHSEngine("data/models/deepghs_rating/model.onnx", threads=1)
    engine.load()
    report = {"python": platform.python_version(), "pillow": pillow_version, "numpy": np.__version__,
              "iterations_per_method": args.iterations, "model_threads": 1,
              "timing_scope": "decode/exif/white RGB/resize/CHW normalization; no inference or download",
              "cases": []}
    for name, image, save_options in samples():
        buffer = BytesIO()
        image.save(buffer, format="PNG", **save_options)
        data = buffer.getvalue()
        outputs = {method: render(data, method) for method in METHODS}
        baseline = np.array(outputs["reference"], dtype=np.int16)
        baseline_tensor = _rgb_tensor(outputs["reference"])
        baseline_scores = engine.infer_tensor(baseline_tensor)
        row = {"name": name, "size": list(image.size), "mode": image.mode, "encoded_bytes": len(data),
               "decode_only_ms": average(lambda: decode_only(data), args.iterations), "methods": {}}
        # Rotate methods each iteration to reduce fixed order bias.
        timings = {method: [] for method in METHODS}
        for method in METHODS:
            for _ in range(2):
                _rgb_tensor(render(data, method))
        for iteration in range(args.iterations):
            methods = list(METHODS)
            methods = methods[iteration % 3:] + methods[:iteration % 3]
            for method in methods:
                started = perf_counter()
                _rgb_tensor(render(data, method))
                timings[method].append((perf_counter() - started) * 1000)
        for method, output in outputs.items():
            difference = np.abs(np.array(output, dtype=np.int16) - baseline)
            tensor = _rgb_tensor(output)
            scores = engine.infer_tensor(tensor)
            row["methods"][method] = {
                "mean_ms": float(np.mean(timings[method])),
                "p95_ms": float(np.percentile(timings[method], 95)),
                "max_pixel_channel_difference": int(difference.max()),
                "mean_pixel_channel_difference": float(difference.mean()),
                "changed_pixel_fraction": float(np.any(difference > 0, axis=2).mean()),
                "tensor_bit_identical": bool(np.array_equal(tensor, baseline_tensor)),
                "scores": scores,
                "max_probability_difference": max(abs(scores[k] - baseline_scores[k]) for k in scores),
                "same_label": max(scores, key=scores.get) == max(baseline_scores, key=baseline_scores.get),
            }
        report["cases"].append(row)
        print(name, {k: round(v["mean_ms"], 2) for k, v in row["methods"].items()}, flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
