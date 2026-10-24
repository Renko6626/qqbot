"""Shared local image albums; independent of business plugins and HTTP."""
from datetime import datetime, timezone
import errno
from io import BytesIO
import json
from pathlib import Path
import random
import re
from typing import Annotated
from uuid import uuid4

from pydantic import StringConstraints

ALBUM_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"
AlbumId = Annotated[str, StringConstraints(pattern=ALBUM_PATTERN)]
EXTENSIONS = {"PNG": ".png", "JPEG": ".jpg", "GIF": ".gif", "WEBP": ".webp",
              "BMP": ".bmp", "TIFF": ".tiff", "AVIF": ".avif"}
IMAGE_PATTERN = r"^[0-9a-f]{32}\.(?:png|jpg|gif|webp|bmp|tiff|avif)$"


class InvalidAlbumImage(ValueError):
    pass


class AlbumNotEmptyError(ValueError):
    pass


class AlbumStore:
    def __init__(self, root: Path):
        self.root = root

    def _directory(self, album: str) -> Path:
        if not re.fullmatch(ALBUM_PATTERN, album):
            raise ValueError("图集 ID 只允许 1 至 64 个英文字母、数字、下划线和短横线")
        return self.root / album

    def create_album(self, album: str) -> dict:
        self._directory(album).mkdir(parents=True, exist_ok=True)
        return {"id": album}

    def list_albums(self) -> list[dict]:
        if not self.root.exists():
            return []
        return [{"id": path.name} for path in sorted(self.root.iterdir())
                if path.is_dir() and re.fullmatch(ALBUM_PATTERN, path.name)]

    def add_image(self, album: str, data: bytes, *, source: str,
                  metadata: dict | None = None) -> dict:
        from PIL import Image, UnidentifiedImageError

        directory = self._directory(album)
        try:
            with Image.open(BytesIO(data)) as image:
                image_format = image.format
                if image_format not in EXTENSIONS:
                    raise InvalidAlbumImage("不支持此图片格式")
                image.verify()
        except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as exc:
            raise InvalidAlbumImage("图片无效或无法读取") from exc
        image_id = uuid4().hex + EXTENSIONS[image_format]
        record = {"id": image_id, "image_file": image_id, "album": album,
                  "format": image_format, "size": len(data),
                  "created_at": datetime.now(timezone.utc).isoformat(),
                  "source": source, "metadata": metadata or {}}
        content = json.dumps(record, ensure_ascii=False, indent=2) + "\n"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / image_id
        path.write_bytes(data)
        path.with_suffix(".json").write_text(content, encoding="utf-8")
        return record

    def list_images(self, album: str) -> list[dict]:
        directory = self._directory(album)
        if not directory.exists():
            return []
        records = []
        for path in sorted(directory.glob("*.json")):
            record = json.loads(path.read_text(encoding="utf-8"))
            # Only return records whose image still exists after manual cleanup.
            if self.image_path(album, record["id"]).is_file():
                records.append(record)
        return records

    def image_path(self, album: str, image_id: str) -> Path:
        directory = self._directory(album)
        if not re.fullmatch(IMAGE_PATTERN, image_id):
            raise ValueError("图片 ID 无效")
        return directory / image_id

    def random_image(self, album: str) -> Path | None:
        directory = self._directory(album)
        if not directory.exists():
            return None
        images = [path for path in directory.iterdir()
                  if path.is_file() and re.fullmatch(IMAGE_PATTERN, path.name)]
        return random.choice(images) if images else None

    def delete_image(self, album: str, image_id: str) -> None:
        path = self.image_path(album, image_id)
        path.unlink()
        path.with_suffix(".json").unlink(missing_ok=True)

    def delete_album(self, album: str) -> None:
        try:
            self._directory(album).rmdir()
        except OSError as exc:
            if exc.errno in {errno.ENOTEMPTY, errno.EEXIST}:
                raise AlbumNotEmptyError("图集中还有文件，请先删除图片") from exc
            raise
