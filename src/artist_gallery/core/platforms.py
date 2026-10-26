"""内置平台定义。

内置平台的识别规则、URL 模板写在代码里，每次打开图库时同步进 platform 表
（`db.sync_builtin_platforms`）。这样改规则只需更新程序，旧图库（包括手机上的）
自动生效，不必为每次调整正则写数据库迁移。
用户自定义平台仍然存在 platform 表里（builtin = 0），规则取自表中的 file_regex。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# 所有内置正则都用 re.ASCII：\d 只匹配 0-9，避免全角数字等被当成 ID。
_A = re.ASCII

# Pixiv 作品 ID 的合理范围：8 位（2010 年起），或 1 开头的 9 位（截至 2026 年约 1.4 亿）。
# 7 位及以下太老、太容易和别的数字撞；10 位多为 Unix 时间戳。
# TODO(约 2029 年)：Pixiv 进入 2 开头的 9 位后需放宽。
PIXIV_ID = r"(?:[1-9][0-9]{7}|1[0-9]{8})"
# X 的推文 ID（snowflake）：2011 年后为 17–19 位。15–16 位的多是其他 App 导出的时间戳。
X_ID = r"[0-9]{17,20}"


@dataclass(frozen=True)
class Rule:
    platform: str
    pattern: re.Pattern[str]
    page_offset: int = 0  # 文件名里的页码从 1 开始时设为 -1
    # True：文件名含"账号类"字样时降为中置信（见 recognize.ACCOUNT_HINT）
    guarded: bool = False


@dataclass(frozen=True)
class PlatformDef:
    id: str
    name: str
    post_url: str | None
    user_url: str | None
    url_regex: str | None
    file_rules: tuple[Rule, ...] = ()


def _rule(platform: str, pattern: str, page_offset: int = 0, *, guarded: bool = False) -> Rule:
    return Rule(platform, re.compile(pattern, _A), page_offset, guarded)


BUILTIN_PLATFORMS: tuple[PlatformDef, ...] = (
    PlatformDef(
        "pixiv",
        "Pixiv",
        "https://www.pixiv.net/artworks/{post_id}",
        "https://www.pixiv.net/users/{uid}",
        r"pixiv\.net/(?:\w+/)?artworks/(?P<post_id>\d+)",
        (
            # 多页 / 原图：标题_ID_pN（也覆盖 ID_pN_master1200 预览图）
            _rule("pixiv", r"(?<![0-9])(?P<post_id>[0-9]{6,10})_p(?P<page>[0-9]+)"),
            # 单页另存：标题_ID（ID 在末尾）。8–9 位数字和 QQ 号撞车，所以加防护
            _rule("pixiv", rf"_(?P<post_id>{PIXIV_ID})$", guarded=True),
        ),
    ),
    PlatformDef(
        "x",
        "X",
        "https://x.com/i/status/{post_id}",
        "https://x.com/i/user/{uid}",
        r"(?:x|twitter)\.com/(?P<handle>\w+)/status/(?P<post_id>\d+)",
        (
            # gallery-dl 下载 X 的默认文件名 {tweet_id}_{num}，num 从 1 开始
            _rule("x", rf"^(?P<post_id>{X_ID})_(?P<page>[0-9]{{1,2}})$", page_offset=-1),
        ),
    ),
    PlatformDef(
        "zerochan",
        "Zerochan",
        "https://www.zerochan.net/{post_id}",
        None,
        r"zerochan\.net/(?P<post_id>\d+)",
        (
            # 名字.full.ID / 名字.600.ID
            _rule("zerochan", r"\.(?:full|[0-9]{3,4})\.(?P<post_id>[0-9]{5,9})$"),
        ),
    ),
)

BUILTIN_BY_ID: dict[str, PlatformDef] = {p.id: p for p in BUILTIN_PLATFORMS}
