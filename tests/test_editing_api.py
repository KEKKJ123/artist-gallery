"""核查写接口及跨站请求边界。"""

import pytest
from PIL import Image
from starlette.testclient import TestClient

from artist_gallery.core import db
from artist_gallery.core.importer import import_files
from artist_gallery.server.app import create_app


@pytest.fixture
def client(tmp_path):
    root = tmp_path / "lib"
    db.init_library(root)
    path = tmp_path / "123456789_p0.png"
    Image.new("RGB", (12, 10), "red").save(path)
    import_files(root, [path])
    with TestClient(create_app(root)) as c:
        c.headers["x-artist-gallery"] = "1"
        c.headers["x-gallery-library"] = c.get("/api/library").json()["library_id"]
        yield c


def test_review_archive_undo_round_trip(client):
    item = client.get("/api/images/1").json()
    assert client.get("/api/images/1/size").json()["bytes"] > 0
    saved = client.post(
        "/api/review/save",
        json={
            "ids": [1],
            "revisions": {"1": item["revision"]},
            "edits": [{"id": item["sources"][0]["id"], "status": "confirmed", "page": None}],
        },
    )
    assert saved.status_code == 200
    assert saved.json()["items"][0]["state"] == "inbox"
    plan = client.post("/api/archive/plan", json={"ids": [1]}).json()
    assert not plan["errors"]
    done = client.post("/api/archive", json={"ids": [1], "token": plan["token"]})
    assert done.status_code == 200
    assert client.get("/api/archived").json()["total"] == 1
    archived = client.get("/api/images/1").json()
    assert client.get(archived["file_url"]).status_code == 200
    assert client.post("/api/undo", json={"id": done.json()["operation_id"]}).status_code == 200
    assert client.get("/api/inbox").json()["total"] == 1
    assert client.post("/api/undo", json={"id": saved.json()["operation_id"]}).status_code == 200


def test_draft_persists_without_confirming(client):
    meta = client.get("/api/library").json()
    assert meta["library_id"]
    r = client.put("/api/images/1/draft", json={"payload": {"text": "unsaved"}, "revision": 0})
    assert r.status_code == 200
    assert client.get("/api/images/1/draft").json()["payload"]["text"] == "unsaved"
    assert client.put("/api/images/1/draft", json={"payload": {}, "revision": 0}).status_code == 409
    assert client.get("/api/images/1").json()["sources"][0]["status"] == "pending"


@pytest.mark.parametrize("origin", ["https://evil.example", "null", "http://testserver.evil"])
def test_cross_site_write_rejected(client, origin):
    assert client.post("/api/review/save", json={}, headers={"origin": origin}).status_code == 403


def test_missing_custom_header_rejected(client):
    del client.headers["x-artist-gallery"]
    assert client.post("/api/review/save", json={}).status_code == 403


@pytest.mark.parametrize("body", ["[]", "null", "{bad", "NaN"])
def test_bad_json_rejected(client, body):
    assert (
        client.post(
            "/api/review/save", content=body, headers={"content-type": "application/json"}
        ).status_code
        == 400
    )


def test_body_limit_and_content_type(client):
    assert client.post("/api/review/save", content="x").status_code == 415
    assert (
        client.post(
            "/api/review/save",
            content="x" * (1024 * 1024 + 1),
            headers={"content-type": "application/json"},
        ).status_code
        == 413
    )


def test_wrong_library_never_writes(client):
    response = client.put(
        "/api/images/1/draft",
        json={"payload": {"text": "wrong"}, "revision": 0},
        headers={"x-gallery-library": "another-library"},
    )
    assert response.status_code == 409
    assert client.get("/api/images/1/draft").json()["payload"] is None


def test_invalid_ids_and_missing_revision_never_write(client):
    for ids in [None, [], [True], [1, 1], ["1"]]:
        assert client.post("/api/review/save", json={"ids": ids}).status_code == 400
    assert client.post("/api/review/save", json={"ids": [1], "revisions": {}}).status_code == 409
    assert client.get("/api/images/1").json()["sources"][0]["status"] == "pending"
