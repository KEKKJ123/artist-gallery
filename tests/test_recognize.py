"""识别规则测试。用例大多取自 2026-10-26 红豆提供的 188 个真实文件名样本。"""

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


H, M, N = "high", "medium", "none"


@pytest.mark.parametrize(
    ("stem", "expected"),
    [
        # --- Pixiv 多页：标题_ID_pN ---
        ("123456789_p0", (H, "pixiv", "123456789", 0)),
        ("方舟漫画作戦記録『ヴィグナは労わりたい編』_107517372_p1", (H, "pixiv", "107517372", 1)),
        ("Sancheck #11 _ WAAAH! VIGNAAA!!!_91723142_p9", (H, "pixiv", "91723142", 9)),
        ("C100\u3000お品書き_100149644_p2", (H, "pixiv", "100149644", 2)),
        ("123456789_p0_master1200", (H, "pixiv", "123456789", 0)),  # 预览图，画质标记见设计 10.1
        # --- Pixiv 单页：标题_ID ---
        ("红豆_80742555", (H, "pixiv", "80742555", 0)),
        ("🍉🍉_121528666", (H, "pixiv", "121528666", 0)),
        ("1_108134360", (H, "pixiv", "108134360", 0)),
        ("ヴィグナ (Vigna)_105328748", (H, "pixiv", "105328748", 0)),
        ("Happy Birthday_ Vigna!!!_125236189", (H, "pixiv", "125236189", 0)),
        # --- 本程序生成的文件名（含重名后缀）---
        ("pixiv_123456789_p3", (H, "pixiv", "123456789", 3)),
        ("x_1849000000000000000_p1", (H, "x", "1849000000000000000", 1)),
        ("x_1849000000000000000_p0_2", (H, "x", "1849000000000000000", 0)),
        # --- gallery-dl 下载 X：序号从 1 开始 → 页码 0 ---
        ("1849000000000000000_1", (H, "x", "1849000000000000000", 0)),
        ("1849000000000000000_4", (H, "x", "1849000000000000000", 3)),
        # --- Zerochan ---
        ("Vigna.full.3017022", (H, "zerochan", "3017022", 0)),
        ("Vigna.600.2844167", (H, "zerochan", "2844167", 0)),
        # --- 单页规则遇到"账号类"字样 → 降为中置信 ---
        ("QQ头像_12345678", (M, "pixiv", "12345678", 0)),
        ("qq_123456789", (M, "pixiv", "123456789", 0)),
        ("微信群_87654321", (M, "pixiv", "87654321", 0)),
        ("avatar_12345678", (M, "pixiv", "12345678", 0)),
        ("头像_12345678_p0", (H, "pixiv", "12345678", 0)),  # 带 _pN 是 Pixiv 原图格式，不降级
        # 防护词不能误伤普通标题
        ("ロドス群像_12345678", (H, "pixiv", "12345678", 0)),
        ("Fluid Guide_12345678", (H, "pixiv", "12345678", 0)),
        ("UID_12345678", (M, "pixiv", "12345678", 0)),
        # --- 中置信 ---
        ("红豆123456789", (M, "pixiv", "123456789", 0)),
        ("【红豆】作品名 (12345678)", (M, "pixiv", "12345678", 0)),
        ("tweet 1849000000000000000", (M, "x", "1849000000000000000", 0)),
        ("EO2cBcJWoAAJJWf", (M, "x", None, None)),  # X 网页另存的 media key
        # --- 不识别：哈希、时间戳、App 导出名 ---
        ("1b82802012ab65ab79072a7eccb18260ac88c5c5", (N, None, None, None)),
        ("fd7209fb10c3a43e05d52f09dbf35cdf498152615", (N, None, None, None)),
        ("4E2EC24E7A6DCD7707BD6110512C4DB2_0", (N, None, None, None)),
        ("B4D5B48A3DD9DFCF0494937BCBDD7CE1_0", (N, None, None, None)),
        ("1749649162592--854060295", (N, None, None, None)),
        (
            "img-1745920240496c3f5e001608558ddec8f79611d7a8be5ba055ae6b3a4bbbaa64b6152043873c2",
            (N, None, None, None),
        ),
        ("Image_107017529707664", (N, None, None, None)),  # QQ 导出，15 位非推文 ID
        ("Image_456995297337559_1744121214245", (N, None, None, None)),
        ("mmexport1738414323347", (N, None, None, None)),
        ("image_editor_1732200296982", (N, None, None, None)),
        ("plpl_cover_20251011015216", (N, None, None, None)),
        ("IMG_20250125_112825", (N, None, None, None)),
        ("Screenshot_2025-03-24-18-52-39-785_ceui.lisa.pixiv-edit", (N, None, None, None)),
        ("Screenshot_20261026_183000", (N, None, None, None)),
        ("1729900000", (N, None, None, None)),  # 10 位时间戳
        ("abc_123_p0", (N, None, None, None)),
        ("立绘_红豆_1", (N, None, None, None)),
        ("XWB1di0x_400x400", (N, None, None, None)),
        ("d0fb090a-111d-4e68-a7fb-56fe9da3bae2_base_resized", (N, None, None, None)),
    ],
)
def test_recognize(rules, stem, expected):
    r = recognize(stem, rules)
    assert (r.confidence.value, r.platform, r.post_id, r.page) == expected


def test_unknown_platform_prefix_falls_through(rules):
    # 'lofter' 尚未登记，不能按本程序格式解析，但里面的 Pixiv 风格部分仍可识别
    r = recognize("lofter_123456789_p0", rules)
    assert r.confidence is Confidence.HIGH and r.platform == "pixiv"
