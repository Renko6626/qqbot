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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("data/models/deepghs_rating"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    destination = args.output_dir / "model.onnx"
    if destination.exists() and hashlib.file_digest(destination.open("rb"), "sha256").hexdigest() == SHA256:
        print(f"Verified existing model: {destination}")
        return
    temporary = destination.with_suffix(".onnx.part")
    try:
        with urllib.request.urlopen(URL, timeout=60) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output)
        if temporary.stat().st_size != SIZE or hashlib.file_digest(temporary.open("rb"), "sha256").hexdigest() != SHA256:
            raise ValueError("Model size or SHA-256 mismatch")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Verified model: {destination} ({SIZE} bytes)")
    print("Source: deepghs/anime_rating / mobilenetv3_sce_dist, model-card license MIT")


if __name__ == "__main__":
    main()
