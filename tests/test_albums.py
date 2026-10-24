from io import BytesIO

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
import pytest

from qqbot.admin import register_admin
from qqbot.albums import AlbumStore, InvalidAlbumImage
from qqbot.runtime import Runtime
from qqbot.settings import PluginStore


def png(color="blue"):
    output = BytesIO()
    Image.new("RGB", (4, 4), color).save(output, format="PNG")
    return output.getvalue()


def test_albums_preserve_originals_metadata_and_keep_collections_separate(tmp_path):
    albums = AlbumStore(tmp_path / "albums")
    assert albums.list_albums() == []
    assert albums.list_images("empty") == []
    assert albums.random_image("empty") is None
    assert not albums.root.exists()
    albums.create_album("empty")
    record = albums.add_image("goodnight", png(), source="test", metadata={"group_id": "12345"})
    albums.add_image("other", png("red"), source="test")
    restored = AlbumStore(albums.root)
    assert restored.list_albums() == [{"id": "empty"}, {"id": "goodnight"}, {"id": "other"}]
    assert restored.list_images("goodnight") == [record]
    assert record["format"] == "PNG" and record["metadata"] == {"group_id": "12345"}
    path = restored.random_image("goodnight")
    assert path.name == record["id"] and path.read_bytes() == png()


def test_invalid_image_and_path_do_not_create_files(tmp_path):
    albums = AlbumStore(tmp_path / "albums")
    with pytest.raises(InvalidAlbumImage):
        albums.add_image("goodnight", b"not an image", source="upload")
    with pytest.raises(ValueError):
        albums.create_album("../escape")
    with pytest.raises(ValueError):
        albums.image_path("goodnight", "../secret")
    assert not albums.root.exists()


@pytest.fixture
def album_api(tmp_path):
    app = FastAPI()
    runtime = Runtime(PluginStore(tmp_path / "plugins.json"))
    register_admin(app, runtime, "operator", "test-password", "")
    with TestClient(app) as http:
        yield http, runtime.albums


def test_album_api_upload_list_and_view_share_authenticated_storage(album_api):
    http, albums = album_api
    assert http.get("/api/albums").status_code == 401
    assert http.post("/api/albums/night/images", content=png()).status_code == 401
    http.auth = ("operator", "test-password")
    assert http.post("/api/albums", json={"id": "night"}).status_code == 403
    http.headers["X-Requested-With"] = "qqbot-admin"
    assert http.post("/api/albums", json={"id": "night"}).json() == {"id": "night"}
    response = http.post("/api/albums/night/images", content=png(), headers={"Content-Type": "image/png"})
    assert response.status_code == 201
    record = response.json()
    assert http.get("/api/albums").json() == [{"id": "night"}]
    assert http.get("/api/albums/night/images").json() == [record]
    assert record["source"] == "upload" and record["metadata"] == {}
    assert http.get(record["url"]).content == png()
    assert albums.random_image("night").read_bytes() == png()
    http.auth = None
    assert http.get(record["url"]).status_code == 401


def test_album_api_rejects_invalid_uploads_and_names(album_api):
    http, albums = album_api
    http.auth = ("operator", "test-password")
    http.headers["X-Requested-With"] = "qqbot-admin"
    assert http.post("/api/albums/night/images", content=b"invalid").status_code == 422
    assert http.post("/api/albums/night/images", content=b"x" * (10 * 1024 * 1024 + 1)).status_code == 413
    assert http.post("/api/albums", json={"id": "../escape"}).status_code == 422
    assert http.get("/api/albums/invalid.name/images").status_code == 422
    assert http.get("/api/albums/night/images/missing.png").status_code == 404
    assert albums.list_albums() == []


def test_delete_requires_auth_and_removes_only_selected_image_and_empty_album(album_api):
    http, albums = album_api
    image = albums.add_image("night", png(), source="upload")
    other = albums.add_image("other", png("red"), source="anime_rating_watch")
    url = f"/api/albums/night/images/{image['id']}"
    assert http.delete(url).status_code == 401
    assert http.delete("/api/albums/night").status_code == 401
    http.auth = ("operator", "test-password")
    assert http.delete(url).status_code == 403
    assert http.delete("/api/albums/night").status_code == 403
    http.headers["X-Requested-With"] = "qqbot-admin"
    assert http.delete("/api/albums/night").status_code == 409
    assert http.get(url).content == png()
    assert http.delete(url).status_code == 200
    assert http.get(url).status_code == 404
    assert albums.list_images("night") == []
    assert albums.random_image("night") is None
    assert list((albums.root / "night").iterdir()) == []
    assert http.delete("/api/albums/night").status_code == 200
    assert albums.list_albums() == [{"id": "other"}]
    assert albums.list_images("other") == [other]
    assert albums.random_image("other").read_bytes() == png("red")
