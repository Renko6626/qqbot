#!/usr/bin/env python3
"""Offline style-gate replay. Images stay local; no bot settings are changed."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import platform
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import onnxruntime as ort
from qqbot.image_rating.engine import _rgb_tensor, decode_image
from benchmark_deepghs import timing, rss_mib
from fetch_deepghs_model import GATE_REVISION, GATE_SHA256

LABELS = ("3d", "bangumi", "comic", "illustration", "not_painting")
ALLOWED_2D = {"bangumi", "comic", "illustration"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=Path("data/models/deepghs_gate/model.onnx"))
    parser.add_argument("--manifest", type=Path, required=True,
                        help="Local JSON list: index, file (relative to manifest), scores (old rating)")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    digest = hashlib.file_digest(args.model.open("rb"), "sha256").hexdigest()
    if digest != GATE_SHA256:
        raise ValueError("Gate model differs from the pinned SHA256")
    records = json.loads(args.manifest.read_text())
    if not records:
        parser.error("manifest is empty")
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    options.add_session_config_entry("session.intra_op.allow_spinning", "0")
    options.add_session_config_entry("session.inter_op.allow_spinning", "0")
    for name, size in [("batch", 1), ("height", 384), ("width", 384)]:
        options.add_free_dimension_override_by_name(name, size)
    started = perf_counter()
    session = ort.InferenceSession(str(args.model), options, providers=["CPUExecutionProvider"])
    setup_ms = (perf_counter() - started) * 1000
    input_meta, output_meta = session.get_inputs(), session.get_outputs()
    if (len(input_meta) != 1 or input_meta[0].shape != [1, 3, 384, 384]
            or input_meta[0].type != "tensor(float)" or len(output_meta) != 1
            or output_meta[0].shape != [1, 5]):
        raise ValueError("Unexpected gate model input/output")

    def infer(tensor):
        values = session.run([output_meta[0].name], {input_meta[0].name: tensor})[0].reshape(-1)
        if (values.shape != (5,) or not np.isfinite(values).all() or np.any(values < 0)
                or np.any(values > 1) or not np.isclose(values.sum(), 1, atol=0.001)):
            raise ValueError("Unexpected gate probabilities")
        return dict(zip(LABELS, map(float, values)))

    warm_tensor = np.zeros((1, 3, 384, 384), dtype=np.float32)
    for _ in range(5):
        infer(warm_tensor)
    results = []
    for record in records:
        started = perf_counter()
        data = (args.manifest.parent / record["file"]).read_bytes()
        image, first_frame_only = decode_image(data, 4_000_000, size=384)
        tensor = _rgb_tensor(image)
        infer_started = perf_counter()
        scores = infer(tensor)
        inference_ms = (perf_counter() - infer_started) * 1000
        total_ms = (perf_counter() - started) * 1000
        label = max(scores, key=scores.get)
        results.append({"index": record["index"], "gate_label": label,
                        "gate_scores": scores, "old_rating_scores": record["scores"],
                        "inference_ms": inference_ms, "local_file_to_scores_ms": total_ms,
                        "first_frame_only": first_frame_only})
    policies = []
    for name, allowed in [("2d_only", ALLOWED_2D), ("2d_and_3d", ALLOWED_2D | {"3d"})]:
        for threshold in [0.8, 0.9, 0.95]:
            passed = [r["index"] for r in results
                      if sum(r["gate_scores"][label] for label in allowed) >= threshold]
            policies.append({"policy": name, "score": "sum_of_allowed_classes", "threshold": threshold,
                             "passed_count": len(passed), "passed_indices": passed,
                             "blocked_count": len(results) - len(passed)})
    report = {"model": "deepghs/anime_classification/mobilenetv3_v1.5_dist",
              "revision": GATE_REVISION, "sha256": digest,
              "python": platform.python_version(), "onnxruntime": ort.__version__,
              "cpu": next(line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                          if line.startswith("model name")),
              "threads": 1, "input": [1, 3, 384, 384], "model_setup_ms": setup_ms,
              "sample_count": len(results), "labels": dict(collections.Counter(r["gate_label"] for r in results)),
              "policies": policies, "results": results,
              "tensor_benchmark_50_runs": timing(lambda: infer(tensor), 50),
              "final_rss_mib": rss_mib()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ["sample_count", "labels", "policies",
                                                 "tensor_benchmark_50_runs"]}, indent=2))


if __name__ == "__main__":
    main()
