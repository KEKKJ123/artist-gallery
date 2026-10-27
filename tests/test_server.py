"""server 层测试：收件箱列表、缩略图、原图、安全边界。"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image
from starlette.testclient import TestClient

from artist_gallery.core import db
from artist_gallery.core.importer import import_files
from artist_gallery.server.app import create_app


def _png(path: Path, color: tuple[int, int, int], size: tuple[int, int] = (64, 48)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path)
    return path


@pytest.fixture
def lib(tmp_path: Path) -> Path:
    """带 3 张图的图库：1 张自动归档、2 张收件箱（其中 1 张是 GIF）。"""
    root = tmp_path / "lib"
    db.init_library(root)
    src = tmp_path / "src"
    _png(src / "红豆 和 空格_12345678_p0.png", (255, 0, 0))  # 自动归档
    _png(src / "截图 1.png", (0, 255, 0))
    Image.new("P", (10, 10)).save(src / "anim.gif")
    import_files(root, [src])
    return root


@pytest.fixture
def client(lib: Path) -> TestClient:
    return TestClient(create_app(lib))


class TestInbox:
    def test_lists_only_inbox(self, client: TestClient) -> None:
        data = client.get("/api/inbox").json()
        assert data["total"] == 3  # 识别成功也进入收件箱
        names = {i["orig_name"] for i in data["items"]}
        assert names == {"截图 1.png", "anim.gif", "红豆 和 空格_12345678_p0.png"}

    def test_thumb_url_only_for_static(self, client: TestClient) -> None:
        items = {i["orig_name"]: i for i in client.get("/api/inbox").json()["items"]}
        assert items["截图 1.png"]["thumb_url"].startswith("/thumbs/")
        assert items["anim.gif"]["thumb_url"] is None

    def test_pagination(self, client: TestClient) -> None:
        data = client.get("/api/inbox?offset=1&limit=1").json()
        assert data["total"] == 3 and len(data["items"]) == 1

    def test_limit_is_capped(self, client: TestClient) -> None:
        assert client.get("/api/inbox?limit=999999").json()["limit"] == 500

    def test_bad_params_400(self, client: TestClient) -> None:
        assert client.get("/api/inbox?offset=abc").status_code == 400

    def test_file_url_is_fetchable(self, client: TestClient) -> None:
        """中文 + 空格的文件名，返回的 URL 要能直接请求到。"""
        item = next(
            i for i in client.get("/api/inbox").json()["items"] if i["orig_name"] == "截图 1.png"
        )
        assert client.get(item["file_url"]).status_code == 200


class TestThumbs:
    def test_generates_webp(self, client: TestClient, lib: Path) -> None:
        item = next(i for i in client.get("/api/inbox").json()["items"] if i["thumb_url"])
        r = client.get(item["thumb_url"])
        assert r.status_code == 200
        assert r.headers["content-type"] == "image/webp"
        assert "immutable" in r.headers["cache-control"]
        assert any((lib / ".cache" / "thumbs").rglob("*.webp"))

    def test_gif_has_no_thumb_204(self, client: TestClient, lib: Path) -> None:
        conn = db.open_library(lib)
        sha = conn.execute("SELECT sha256 FROM image_file WHERE rel_path LIKE '%.gif'").fetchone()[
            0
        ]
        conn.close()
        assert client.get(f"/thumbs/{sha}").status_code == 204

    def test_unknown_sha_404(self, client: TestClient) -> None:
        assert client.get("/thumbs/" + "0" * 64).status_code == 404

    def test_malformed_sha_404(self, client: TestClient) -> None:
        assert client.get("/thumbs/not-a-hash").status_code == 404
        assert client.get("/thumbs/" + "A" * 64).status_code == 404  # 只认小写十六进制

    def test_traversal_does_not_leak_db(self, client: TestClient) -> None:
        # HTTP 客户端 / Starlette 会先规范化路径，请求常落到前端页面（200 HTML）；
        # 关键是任何情况下都读不出数据库内容。
        r = client.get("/thumbs/..%2F..%2Flibrary.db")
        assert b"SQLite format" not in r.content


class TestImages:
    def test_serves_archived_file(self, client: TestClient) -> None:
        r = client.get("/images/_inbox/红豆 和 空格_12345678_p0.png")
        assert r.status_code == 200
        assert r.headers["content-type"] == "image/png"

    def test_missing_404(self, client: TestClient) -> None:
        assert client.get("/images/pixiv/nope.png").status_code == 404

    @pytest.mark.parametrize(
        "path",
        [
            "/images/../library.db",
            "/images/%2e%2e/library.db",
            "/images/..%2Flibrary.db",
            "/images/pixiv/../../library.db",
        ],
    )
    def test_no_path_traversal_via_http(self, client: TestClient, path: str) -> None:
        # 路径经规范化后可能落到前端页面，只要求读不出数据库
        r = client.get(path)
        assert b"SQLite format" not in r.content

    def test_handler_rejects_traversal_directly(self, lib: Path) -> None:
        """绕过 URL 规范化，直接把 ../ 交给处理器：必须返回 403。"""
        from types import SimpleNamespace

        from artist_gallery.server.media import serve_image

        app = create_app(lib)
        fake = SimpleNamespace(app=app, path_params={"rel_path": "../library.db"})
        assert serve_image(fake).status_code == 403  # type: ignore[arg-type]


class TestStateBrowse:
    def test_navigation_counts_suggestions(self, client):
        assert client.get("/api/navigation").json() == {
            "inbox": 3,
            "inbox_hinted": 1,
            "archived": 0,
        }

    def test_archived_is_empty_until_explicit_state_change(self, client, lib):
        assert client.get("/api/archived").json()["total"] == 0
        conn = db.open_library(lib)
        with conn:
            conn.execute("UPDATE image SET state='archived' WHERE id=(SELECT MIN(id) FROM image)")
        conn.close()
        result = client.get("/api/archived").json()
        assert result["total"] == 1
        item = result["items"][0]
        assert item["state"] == "archived"  # 查询不依赖路径
        assert "_inbox/" in item["rel_path"]
        assert client.get(item["file_url"]).status_code == 200
        assert client.get("/api/navigation").json()["archived"] == 1

    @pytest.mark.parametrize("endpoint", ["/api/folders", "/api/folder?path=pixiv"])
    def test_old_folder_routes_are_not_silently_source_queries(self, client, endpoint):
        assert client.get(endpoint).status_code == 404

    def test_bad_numbers(self, client):
        assert client.get("/api/archived?offset=x").status_code == 400


class TestPlatforms:
    def test_lists_builtin(self, client: TestClient) -> None:
        ids = {p["id"] for p in client.get("/api/platforms").json()}
        assert {"pixiv", "x", "zerochan"} <= ids


class TestRouting:
    def test_root_serves_frontend(self, client: TestClient) -> None:
        r = client.get("/")
        assert r.status_code == 200 and "text/html" in r.headers["content-type"]

    def test_unknown_api_is_404_not_html(self, client: TestClient) -> None:
        r = client.get("/api/nope")
        assert r.status_code == 404
        assert r.headers["content-type"].startswith("application/json")

    def test_spa_route_falls_back(self, client: TestClient) -> None:
        assert client.get("/inbox/whatever").status_code == 200


class TestHostCheck:
    def test_foreign_host_rejected(self, lib: Path) -> None:
        c = TestClient(create_app(lib), base_url="http://evil.example.com")
        assert c.get("/api/inbox").status_code == 400

    def test_lan_mode_accepts_any_host(self, lib: Path) -> None:
        c = TestClient(create_app(lib, allow_any_host=True), base_url="http://192.168.1.5:8765")
        assert c.get("/api/inbox").status_code == 200


def test_not_a_library_raises(tmp_path: Path) -> None:
    with pytest.raises(db.NotALibraryError):
        create_app(tmp_path)


class TestInboxFilterApi:
    def test_filter_param(self, client: TestClient) -> None:
        allr = client.get("/api/inbox").json()
        assert allr["filter"] == "all"
        hint = client.get("/api/inbox", params={"filter": "hint"}).json()
        no = client.get("/api/inbox", params={"filter": "nohint"}).json()
        assert hint["filter"] == "hint" and no["filter"] == "nohint"
        assert hint["total"] + no["total"] == allr["total"]

    def test_unknown_filter_400_json(self, client: TestClient) -> None:
        r = client.get("/api/inbox", params={"filter": "bogus"})
        assert r.status_code == 400
        assert r.headers["content-type"].startswith("application/json")
        assert "filter" in r.json()["error"]

    def test_empty_filter_means_all(self, client: TestClient) -> None:
        assert client.get("/api/inbox?filter=").json()["filter"] == "all"

    def test_nav_payload_has_hinted_count(self, client: TestClient) -> None:
        nav = client.get("/api/navigation").json()
        assert "inbox_hinted" in nav and 0 <= nav["inbox_hinted"] <= nav["inbox"]
