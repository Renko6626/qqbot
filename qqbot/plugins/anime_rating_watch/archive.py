"""Store only matched originals and their small, inspectable JSON records."""
from datetime import datetime, timezone
from io import BytesIO
import json
from pathlib import Path
from uuid import uuid4

from PIL import Image

from qqbot.image_rating.service import ImageAnalysis

EXTENSIONS = {"PNG": ".png", "JPEG": ".jpg", "GIF": ".gif", "WEBP": ".webp",
              "BMP": ".bmp", "TIFF": ".tiff", "AVIF": ".avif"}


def save_hit(analysis: ImageAnalysis, root: Path, *, group_id: int, message_id: int) -> Path:
    now = datetime.now(timezone.utc)
    directory = root / str(group_id) / now.strftime("%Y-%m-%d")
    directory.mkdir(parents=True, exist_ok=True)
    with Image.open(BytesIO(analysis.data)) as image:
        image_format = image.format
    stem = f"{message_id}-{uuid4().hex}"
    path = directory / (stem + EXTENSIONS.get(image_format, ".img"))
    path.write_bytes(analysis.data)
    record = {"created_at": now.isoformat(), "group_id": str(group_id),
              "message_id": str(message_id), "image_file": path.name, "format": image_format,
              "label": analysis.result.label, "scores": analysis.result.scores,
              "first_frame_only": analysis.result.first_frame_only}
    path.with_suffix(".json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                                        encoding="utf-8")
    return path
