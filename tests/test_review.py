"""来源核查、范围、并发、草稿与可连续撤销；所有图片现场生成。"""

import pytest
from PIL import Image

from artist_gallery.core import db, drafts, review
from artist_gallery.core import operations as ops
from artist_gallery.core.importer import import_files


@pytest.fixture
def lib(tmp_path):
    root = tmp_path / "lib"
    db.init_library(root)
    src = tmp_path / "source"
    src.mkdir()
    for name, color in [("123456789_p2.png", "red"), ("other.png", "blue"), ("third.png", "green")]:
        Image.new("RGB", (10, 10), color).save(src / name)
    import_files(root, [src])
    conn = db.open_library(root)
    yield root, conn
    conn.close()


def revisions(conn, ids):
    return {str(i): ops.revision(conn, i) for i in ids}


@pytest.mark.parametrize(
    "url,platform,post,page",
    [
        ("https://www.pixiv.net/artworks/123456789", "pixiv", "123456789", None),
        ("https://www.pixiv.net/en/artworks/123456789?utm=x", "pixiv", "123456789", None),
        (
            "https://twitter.com/name/status/1849000000000000000/photo/2",
            "x",
            "1849000000000000000",
            1,
        ),
        ("https://x.com/i/web/status/1849000000000000000", "x", "1849000000000000000", None),
        ("https://www.zerochan.net/3017022", "zerochan", "3017022", None),
    ],
)
def test_parse_known_links(lib, url, platform, post, page):
    _, conn = lib
    result = review.parse_links(conn, url)[0]
    assert (result["platform"], result["post_id"], result["page"]) == (platform, post, page)


@pytest.mark.parametrize(
    "url",
    [
        "https://www.pixiv.net/users/123456789",
        "https://evil.com/pixiv.net/artworks/123456789",
        "https://pixiv.net.evil.com/artworks/123456789",
        "javascript:alert(1)",
        "https://user@pixiv.net/artworks/123456789",
        "https://x.com/a/status/123/photo/0",
        "https://x.com/a/status/123/photo/99999999999999999999999999999",
        "123456789",
    ],
)
def test_reject_non_post_or_spoofed_links(lib, url):
    assert "error" in review.parse_links(lib[1], url)[0]


def test_bad_lines_do_not_block_good_pending_links(lib):
    _, conn = lib
    result = review.save(
        conn, [2], revisions(conn, [2]), text="wrong\nhttps://x.com/a/status/1849000000000000000"
    )
    assert "error" in result["lines"][0]
    item = result["items"][0]
    assert item["state"] == "inbox" and item["sources"][0]["status"] == "pending"
    assert item["sources"][0]["page"] is None
    assert item["artist"] is None


def test_bulk_scope_required_and_unselected_untouched(lib):
    _, conn = lib
    text = "https://x.com/a/status/1849000000000000000\nhttps://pixiv.net/artworks/23456789"
    with pytest.raises(ops.OperationError, match="每张"):
        review.save(conn, [1, 2], revisions(conn, [1, 2]), text=text)
    review.save(conn, [1, 2], revisions(conn, [1, 2]), text=text, confirm_scope=True)
    for i in [1, 2]:
        assert {s["platform"] for s in review.detail(conn, i)["sources"]} == {"x", "pixiv"}
    assert review.detail(conn, 3)["sources"] == []


def test_confirm_reject_append_preserves_manual_decisions(lib):
    _, conn = lib
    source = review.detail(conn, 1)["sources"][0]
    review.save(
        conn,
        [1],
        revisions(conn, [1]),
        edits=[{"id": source["id"], "status": "confirmed", "page": None}],
    )
    review.save(conn, [1], revisions(conn, [1]), text="https://pixiv.net/artworks/123456789")
    item = review.detail(conn, 1)
    assert item["sources"][0]["status"] == "confirmed"
    assert item["sources"][0]["page"] is None
    assert item["state"] == "inbox" and not item["source_hints"]
    review.save(conn, [1], revisions(conn, [1]), edits=[{"id": source["id"], "status": "rejected"}])
    assert not review.detail(conn, 1)["source_hints"]


def test_empty_text_does_not_remove_and_removal_explicit_reversible(lib):
    _, conn = lib
    before = review.detail(conn, 1)
    review.save(conn, [1], revisions(conn, [1]), text="")
    assert review.detail(conn, 1)["sources"] == before["sources"]
    result = review.save(
        conn, [1], revisions(conn, [1]), edits=[{"id": before["sources"][0]["id"], "remove": True}]
    )
    assert review.detail(conn, 1)["sources"] == []
    assert review.detail(conn, 1)["source_hints"] == []
    assert review.detail(conn, 1)["evidence"][0]["input_text"]
    ops.undo_review(conn, result["operation_id"])
    assert review.detail(conn, 1)["sources"] == before["sources"]


def test_stale_review_rejected_atomically(lib):
    _, conn = lib
    rev = revisions(conn, [1])
    source = review.detail(conn, 1)["sources"][0]
    review.save(conn, [1], rev, edits=[{"id": source["id"], "status": "confirmed"}])
    with pytest.raises(ops.ConflictError):
        review.save(conn, [1], rev, text="https://x.com/a/status/1849000000000000000")
    assert len(review.detail(conn, 1)["sources"]) == 1


def test_undo_repeated_and_barrier(lib):
    _, conn = lib
    a = review.save(
        conn, [1], revisions(conn, [1]), text="https://x.com/a/status/1849000000000000000"
    )
    b = review.save(conn, [2], revisions(conn, [2]), text="https://pixiv.net/artworks/23456789")
    with pytest.raises(ops.ConflictError):
        ops.undo_review(conn, a["operation_id"])
    ops.undo_review(conn, b["operation_id"])
    ops.undo_review(conn, a["operation_id"])
    assert not ops.latest(conn)["can_undo"]
    assert len(review.detail(conn, 1)["sources"]) == 1


def test_draft_separate_persistent_cas_and_clear(lib):
    root, conn = lib
    before = revisions(conn, [1])
    record = drafts.save(conn, 1, {"text": "https://pixiv.net/artworks/123456789"}, 0)
    assert record["revision"] == 1
    other = db.open_library(root)
    assert drafts.load(other, 1) == record
    assert drafts.load(other, 2)["payload"] is None
    with pytest.raises(ops.ConflictError):
        drafts.save(other, 1, {"text": "old"}, 0)
    drafts.save(other, 1, None, 1)
    with pytest.raises(ops.ConflictError):
        drafts.save(conn, 1, {"text": "stale"}, 0)
    other.close()
    assert before == revisions(conn, [1])


def test_shared_publish_time_requires_exact_scope_and_undo(lib):
    _, conn = lib
    review.save(conn, [2], revisions(conn, [2]), text="https://pixiv.net/artworks/123456789")
    source = review.detail(conn, 1)["sources"][0]
    assert source["time_image_ids"] == [1, 2]
    edit = {"id": source["id"], "posted_at": "2026-10-28T12:00:00+08:00"}
    with pytest.raises(ops.OperationError, match="共享"):
        review.save(conn, [1], revisions(conn, [1]), edits=[edit], confirm_scope=True)
    edit["time_scope_ids"] = [1, 2]
    saved = review.save(conn, [1], revisions(conn, [1]), edits=[edit], confirm_scope=True)
    assert review.detail(conn, 2)["sources"][0]["posted_at"] == edit["posted_at"]
    ops.undo_review(conn, saved["operation_id"])
    assert review.detail(conn, 2)["sources"][0]["posted_at"] is None


@pytest.mark.parametrize("page", [-1, True, 1.5, 1 << 53, "0"])
def test_invalid_page_does_not_write(lib, page):
    _, conn = lib
    before = review.detail(conn, 1)
    with pytest.raises(ops.OperationError):
        review.save(
            conn,
            [1],
            revisions(conn, [1]),
            edits=[{"id": before["sources"][0]["id"], "page": page}],
        )
    assert review.detail(conn, 1) == before
