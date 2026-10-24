#!/usr/bin/env python3
"""Bounded local CPU benchmark. No QQ, network download or VPS access."""
import argparse
from io import BytesIO
import json
import os
from pathlib import Path
import platform
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from PIL import Image
from qqbot.plugins.anime_rating.engine import DeepGHSEngine, preprocess


def rss_mib(field="VmRSS"):
    line = next(s for s in Path("/proc/self/status").read_text().splitlines() if s.startswith(field + ":"))
    return int(line.split()[1]) / 1024


def timing(call, count):
    samples = []
    started = perf_counter()
    for _ in range(count):
        t = perf_counter()
        call()
        samples.append((perf_counter() - t) * 1000)
    elapsed = perf_counter() - started
    return {"images_per_second": count / elapsed, "mean_ms": float(np.mean(samples)),
            "p50_ms": float(np.median(samples)), "p95_ms": float(np.percentile(samples, 95))}


def main():
    import openvino as ov

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=Path("data/models/deepghs_rating/model.onnx"))
    parser.add_argument("--threads", type=int, choices=[1, 2], nargs="+", default=[1, 2])
    parser.add_argument("--iterations", type=int, default=50)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.iterations < 1 or args.warmup < 0:
        parser.error("iterations must be positive and warmup non-negative")
    # Non-sensitive deterministic 512x512 RGB gradient, encoded as PNG.
    x, y = np.meshgrid(np.arange(512), np.arange(512))
    image = Image.fromarray(np.stack((x % 256, y % 256, (x + y) % 256), axis=2).astype(np.uint8))
    buffer = BytesIO(); image.save(buffer, format="PNG"); data = buffer.getvalue()
    tensor = preprocess(image)
    cpu = next((s.split(":", 1)[1].strip() for s in Path("/proc/cpuinfo").read_text().splitlines()
                if s.startswith("model name")), platform.processor())
    report = {"cpu": cpu, "logical_cpus": os.cpu_count(), "allowed_cpus": len(os.sched_getaffinity(0)),
              "python": platform.python_version(), "openvino": ov.__version__, "model": str(args.model),
              "input": [1, 3, 384, 384], "sample": "synthetic 512x512 RGB PNG", "batch": 1,
              "warmup": args.warmup, "iterations": args.iterations, "baseline_rss_mib": rss_mib(), "runs": []}
    for threads in args.threads:
        engine = DeepGHSEngine(args.model, threads=threads)
        t = perf_counter(); engine.load(); cold_ms = (perf_counter() - t) * 1000
        loaded_rss = rss_mib()
        for _ in range(args.warmup): engine.classify(data)
        report["runs"].append({"threads": threads, "streams": 1, "cold_setup_ms": cold_ms, "loaded_rss_mib": loaded_rss, "warmed_rss_mib": rss_mib(),
                               "precision_hint": str(engine._compiled.get_property("INFERENCE_PRECISION_HINT")),
                               "tensor_inference": timing(lambda: engine.infer_tensor(tensor), args.iterations),
                               "decode_preprocess_inference": timing(lambda: engine.classify(data), args.iterations), "final_rss_mib": rss_mib()})
    report["process_peak_hwm_mib"] = rss_mib("VmHWM")
    output = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(output)
    print(output)


if __name__ == "__main__":
    main()
