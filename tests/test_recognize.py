import pytest

from artist_gallery.core import db
from artist_gallery.core.recognize import Confidence, load_rules, recognize


@pytest.fixture(scope="module")
def rules(tmp_path_factory):
    root = tmp_path_factory.mktemp("lib")
    db.init_library(root)
    conn = db.connect(root)
    r = load_rules(conn)
    conn.close()
    return r


@pytest.mark.parametrize(
    ("stem", "expected"),
    [
        # Pixiv 原图文件名
        ("123456789_p0", ("high", "pixiv", "123456789", 0)),
        ("某作品标题_123456789_p2", ("high", "pixiv", "123456789", 2)),
        ("illust_123456789_p10", ("high", "pixiv", "123456789", 10)),
        # 本程序生成的文件名（含重名后缀）
        ("pixiv_123456789_p3", ("high", "pixiv", "123456789", 3)),
        ("x_1849000000000000000_p1", ("high", "x", "1849000000000000000", 1)),
        ("x_1849000000000000000_p0_2", ("high", "x", "1849000000000000000", 0)),
        # gallery-dl 下载 X 的默认格式：序号从 1 开始 → 页码 0
        ("1849000000000000000_1", ("high", "x", "1849000000000000000", 0)),
        ("1849000000000000000_4", ("high", "x", "1849000000000000000", 3)),
        # 中置信：孤立数字
        ("红豆123456789", ("medium", "pixiv", "123456789", 0)),
        ("【红豆】作品名 (12345678)", ("medium", "pixiv", "12345678", 0)),
        ("tweet 1849000000000000000", ("medium", "x", "1849000000000000000", 0)),
        # 未识别
        ("GxAbC12xyzQ", ("none", None, None, None)),  # X 网页右键保存（media key）
        ("Screenshot_20261026_183000", ("none", None, None, None)),  # 日期不当作 Pixiv ID
        ("IMG_20261026", ("none", None, None, None)),
        ("1729900000", ("none", None, None, None)),  # 10 位时间戳
        ("abc_123_p0", ("none", None, None, None)),  # 未登记的平台前缀，数字太短
    ],
)
def test_recognize(rules, stem, expected):
    r = recognize(stem, rules)
    assert (r.confidence.value, r.platform, r.post_id, r.page) == expected


def test_unknown_platform_prefix_falls_through(rules):
    # 'lofter' 尚未登记，不能按本程序格式解析，但里面的 Pixiv 风格部分仍可识别
    r = recognize("lofter_123456789_p0", rules)
    assert r.confidence is Confidence.HIGH and r.platform == "pixiv"
