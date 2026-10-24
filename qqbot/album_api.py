"""Album endpoints, mounted under the existing authenticated admin router."""
from collections.abc import Callable

import anyio
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict

from .albums import AlbumId, AlbumNotEmptyError, AlbumStore, InvalidAlbumImage

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class CreateAlbum(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: AlbumId


def register_album_routes(router: APIRouter, albums: AlbumStore, check_write: Callable) -> None:
    def with_url(record: dict) -> dict:
        return {**record, "url": f"/api/albums/{record['album']}/images/{record['id']}"}

    @router.get("/api/albums")
    def list_albums():
        return albums.list_albums()

    @router.post("/api/albums", dependencies=[Depends(check_write)])
    def create_album(body: CreateAlbum):
        return albums.create_album(body.id)

    @router.get("/api/albums/{album}/images")
    def list_images(album: AlbumId):
        return [with_url(record) for record in albums.list_images(album)]

    @router.post("/api/albums/{album}/images", status_code=201,
                 dependencies=[Depends(check_write)])
    async def upload_image(album: AlbumId, request: Request):
        data = bytearray()
        async for chunk in request.stream():
            if len(data) + len(chunk) > MAX_UPLOAD_BYTES:
                raise HTTPException(413, "图片不能超过 10 MiB")
            data.extend(chunk)
        try:
            record = await anyio.to_thread.run_sync(
                lambda: albums.add_image(album, bytes(data), source="upload"))
        except InvalidAlbumImage:
            raise HTTPException(422, "请上传有效的图片文件") from None
        except OSError:
            raise HTTPException(500, "图片保存失败，请检查数据目录权限") from None
        return with_url(record)

    @router.get("/api/albums/{album}/images/{image_id}")
    def view_image(album: AlbumId, image_id: str):
        try:
            path = albums.image_path(album, image_id)
        except ValueError:
            raise HTTPException(404, "图片不存在") from None
        if not path.is_file():
            raise HTTPException(404, "图片不存在")
        return FileResponse(path, headers={"Cache-Control": "no-store"})

    @router.delete("/api/albums/{album}/images/{image_id}", dependencies=[Depends(check_write)])
    def delete_image(album: AlbumId, image_id: str):
        try:
            albums.delete_image(album, image_id)
        except (ValueError, FileNotFoundError):
            raise HTTPException(404, "图片不存在") from None
        except OSError:
            raise HTTPException(500, "图片删除失败，请检查数据目录权限") from None
        return {"deleted": image_id}

    @router.delete("/api/albums/{album}", dependencies=[Depends(check_write)])
    def delete_album(album: AlbumId):
        try:
            albums.delete_album(album)
        except AlbumNotEmptyError:
            raise HTTPException(409, "图集中还有文件，请先删除图片；可刷新查看最新内容") from None
        except FileNotFoundError:
            raise HTTPException(404, "图集不存在") from None
        except OSError:
            raise HTTPException(500, "图集删除失败，请检查数据目录权限") from None
        return {"deleted": album}
