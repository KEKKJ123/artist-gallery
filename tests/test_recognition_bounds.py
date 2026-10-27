"""来源页码限于可精确往返的整数，异常只影响当前文件。"""

import re
import shutil

import pytest
from PIL import Image

from artist_gallery.core import db
from artist_gallery.core.importer import Action, import_files
from artist_gallery.core.platforms import Rule
from artist_gallery.core.recognize import (
    MAX_PAGE,
    BadRecognition,
    RuleSet,
    _parse_page,
    load_rules,
    recognize,
)


@pytest.mark.parametrize("value", [str(MAX_PAGE + 1), "9" * 5000, "-1", "abc", "１"])
def test_invalid_page_is_explicit_error(value):
    with pytest.raises(BadRecognition):
        _parse_page(value)


@pytest.mark.parametrize(
    ("value", "offset", "expected"),
    [
        (None, 0, None),
        ("", 0, None),
        ("0", 0, 0),
        ("0002", 0, 2),
        (str(MAX_PAGE), 0, MAX_PAGE),
        (str(MAX_PAGE + 1), -1, MAX_PAGE),
        ("1", -1, 0),
    ],
)
def test_page_boundaries(value, offset, expected):
    assert _parse_page(value, offset) == expected


def test_custom_and_builtin_rules_have_same_bounds(tmp_path):
    db.init_library(tmp_path)
    conn = db.open_library(tmp_path)
    try:
        rules = load_rules(conn)
        for prefix in ("pixiv_123456789_p", "123456789_p"):
            with pytest.raises(BadRecognition):
                recognize(prefix + str(MAX_PAGE + 1), rules)
        custom = RuleSet(
            frozenset({"custom"}),
            (Rule("custom", re.compile(r"(?P<post_id>123)_page(?P<page>.*)")),),
        )
        with pytest.raises(BadRecognition):
            recognize("123_pagebad", custom)
    finally:
        conn.close()


@pytest.mark.parametrize("duplicate", [False, True])
@pytest.mark.parametrize("dry_run", [False, True])
def test_bad_page_does_not_abort_batch(tmp_path, duplicate, dry_run):
    root, source = tmp_path / "lib", tmp_path / "source"
    source.mkdir()
    db.init_library(root)
    seed = tmp_path / "seed.png"
    Image.new("RGB", (12, 12), (10, 20, 30)).save(seed)
    if duplicate:
        import_files(root, [seed])
    bad = source / "123456789_p9999999999999999999999999999999.png"
    shutil.copyfile(seed, bad)
    valid = source / "z_valid.png"
    Image.new("RGB", (12, 12), (90, 80, 70)).save(valid)
    report = import_files(root, [source], dry_run=dry_run)
    by_name = {item.src.name: item for item in report.items}
    assert by_name[bad.name].action is Action.ERROR
    assert "页码" in by_name[bad.name].message
    assert by_name[valid.name].action is Action.INBOX
    assert bad.exists()
    if not dry_run:
        assert (root / by_name[valid.name].rel_path).exists()
