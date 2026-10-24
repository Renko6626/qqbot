#!/usr/bin/env python3
"""Fetch a pinned public model; never downloads during bot startup."""
import argparse
import hashlib
from pathlib import Path
import shutil
import urllib.request

REVISION = "46be80bfe01a415efa5aa7c025528cac82a8b88a"
VARIANT = "mobilenetv3_sce_dist"
SHA256 = "31814ba076d65d129b89322a767d55d0669c54015134c117da3cf2717defde4e"
SIZE = 16_827_558
URL = f"https://huggingface.co/deepghs/anime_rating/resolve/{REVISION}/{VARIANT}/model.onnx"
GATE_REVISION = "5ee62e06f5f4cd68a1c2f3bc5dc9805e827d37df"
GATE_VARIANT = "mobilenetv3_v1.5_dist"
GATE_SHA256 = "ea8f4497b0e3ee86f43b6a6fd38884e25f960979a1debb5c4e1ee6a22e80d111"
GATE_SIZE = 16_836_527
GATE_URL = f"https://huggingface.co/deepghs/anime_classification/resolve/{GATE_REVISION}/{GATE_VARIANT}/model.onnx"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=["rating", "gate"], default="rating")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    gate = args.kind == "gate"
    url, size, sha256 = (GATE_URL, GATE_SIZE, GATE_SHA256) if gate else (URL, SIZE, SHA256)
    output_dir = args.output_dir or Path("data/models/deepghs_gate" if gate else "data/models/deepghs_rating")
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / "model.onnx"
    if destination.exists() and hashlib.file_digest(destination.open("rb"), "sha256").hexdigest() == sha256:
        print(f"Verified existing model: {destination}")
        return
    temporary = destination.with_suffix(".onnx.part")
    try:
        with urllib.request.urlopen(url, timeout=60) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output)
        if temporary.stat().st_size != size or hashlib.file_digest(temporary.open("rb"), "sha256").hexdigest() != sha256:
            raise ValueError("Model size or SHA-256 mismatch")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Verified model: {destination} ({size} bytes)")
    print("Source: " + (f"deepghs/anime_classification / {GATE_VARIANT}" if gate
                        else f"deepghs/anime_rating / {VARIANT}") + ", model-card license MIT")


if __name__ == "__main__":
    main()
