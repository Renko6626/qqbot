#!/usr/bin/env python3
"""CPU-only comparison worker; run each backend/thread configuration in a fresh process.

Uses optional evaluation dependencies, without changing the bot's runtime.
"""
import argparse
from io import BytesIO
import hashlib
import importlib
import json
import os
from pathlib import Path
import platform
import sys
from time import perf_counter, process_time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from PIL import Image
from qqbot.plugins.anime_rating.engine import (
    DeepGHSEngine, _rgb_tensor, decode_image, probability_scores,
)
from benchmark_deepghs import rss_mib, timing


def samples():
    for width, height, mode, fmt in [
        (512, 512, "RGB", "PNG"), (1600, 1200, "RGB", "JPEG"),
        (1600, 1200, "RGBA", "PNG"),
    ]:
        y, x = np.indices((height, width))
        image = Image.fromarray(np.stack((x % 256, y % 256, (x + y) % 256), -1).astype("uint8"))
        if mode == "RGBA":
            image = image.convert(mode)
            image.putalpha(128)
        buffer = BytesIO()
        image.save(buffer, format=fmt)
        yield f"{width}x{height}-{mode}-{fmt}", buffer.getvalue()


def prepare(data):
    return _rgb_tensor(decode_image(data, 4_000_000, size=384)[0])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=["openvino", "onnxruntime"], required=True)
    parser.add_argument("--threads", type=int, choices=[1, 2], required=True)
    parser.add_argument("--iterations", type=int, default=40)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--model", type=Path, default=Path("data/models/deepghs_rating/model.onnx"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.iterations < 1 or args.warmup < 0:
        parser.error("iterations must be positive and warmup non-negative")
    report = {"backend": args.backend, "threads": args.threads, "python": platform.python_version(),
              "cpu": next(line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                          if line.startswith("model name")),
              "allowed_cpus": len(os.sched_getaffinity(0)), "input": [1, 3, 384, 384],
              "model_sha256": hashlib.sha256(args.model.read_bytes()).hexdigest(),
              "iterations": args.iterations, "warmup": args.warmup, "runs": []}
    started = perf_counter()
    runtime = importlib.import_module(args.backend)
    report["runtime_import_ms"] = (perf_counter() - started) * 1000
    report["runtime_version"] = runtime.__version__
    report["imported_rss_mib"] = rss_mib()
    started = perf_counter()
    if args.backend == "openvino":
        core = runtime.Core()
        model = core.read_model(str(args.model))
        model.reshape({model.input(0): [1, 3, 384, 384]})
        compiled = core.compile_model(model, "CPU", {
            "INFERENCE_NUM_THREADS": args.threads, "NUM_STREAMS": 1,
            "PERFORMANCE_HINT": "LATENCY",
        })
        request = compiled.create_infer_request()
        output = compiled.output(0)

        def infer(tensor):
            return probability_scores(request.infer({0: tensor})[output])

        report["settings"] = {"streams": 1, "performance_hint": "LATENCY",
                              "precision_hint": str(compiled.get_property("INFERENCE_PRECISION_HINT"))}
    else:
        engine = DeepGHSEngine(args.model, threads=args.threads)
        engine.load()
        infer = engine.infer_tensor
        session = engine._session
        report["settings"] = {"providers": session.get_providers(), "spinning": False,
                              "execution": "SEQUENTIAL", "graph_optimization": "ALL",
                              "resolved_input": session.get_inputs()[0].shape}
    report["model_setup_ms"] = (perf_counter() - started) * 1000
    report["loaded_rss_mib"] = rss_mib()
    for name, data in samples():
        tensor = prepare(data)
        for _ in range(args.warmup):
            infer(tensor)
        started = process_time()
        pure = timing(lambda: infer(tensor), args.iterations)
        pure["process_cpu_ms_per_image"] = (process_time() - started) * 1000 / args.iterations
        started = process_time()
        full = timing(lambda: infer(prepare(data)), args.iterations)
        full["process_cpu_ms_per_image"] = (process_time() - started) * 1000 / args.iterations
        report["runs"].append({"sample": name, "scores": infer(tensor), "tensor_inference": pure,
                               "decode_preprocess_inference": full})
    # Small deterministic diversity check, not a classification accuracy dataset.
    rng = np.random.default_rng(42)
    tensors = [np.full((1, 3, 384, 384), value, dtype=np.float32) for value in [-1, 0, 1]]
    tensors += [rng.uniform(-1, 1, (1, 3, 384, 384)).astype(np.float32) for _ in range(5)]
    report["probe_scores"] = [infer(tensor) for tensor in tensors]
    report["final_rss_mib"] = rss_mib()
    report["process_peak_hwm_mib"] = rss_mib("VmHWM")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"backend": args.backend, "threads": args.threads,
                      "rss_mib": report["final_rss_mib"], "output": str(args.output)}), flush=True)


if __name__ == "__main__":
    main()
