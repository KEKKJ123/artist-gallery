"""从文件名识别作品来源。纯函数：输入文件名（不含扩展名）和规则，输出识别结果。

识别顺序（命中即停）：
1. 本程序自己生成的文件名 `{platform}_{post_id}_p{page}[_后缀]`  → 高置信
2. platform 表里各平台的 file_regex                              → 高置信
3. 内置补充规则（Pixiv `标题_ID`、gallery-dl 的 X 默认文件名）     → 高置信
4. 文件名里孤立的一串数字                                         → 中置信（进收件箱，附建议）
5. 都不匹配                                                       → 无（进收件箱）

"孤立"指数字两侧不是字母或数字：这样十六进制哈希（`1b82802012ab…`）、
`mmexport1738414323347` 之类不会被误认，而 `红豆_80742555`、`红豆123456789` 仍可识别。
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from enum import StrEnum


class Confidence(StrEnum):
    HIGH = "high"  # 自动归档
    MEDIUM = "medium"  # 进收件箱，附带来源建议，等用户确认
    NONE = "none"  # 进收件箱


@dataclass(frozen=True)
class Recognition:
    confidence: Confidence
    platform: str | None = None
    post_id: str | None = None
    page: int | None = None


@dataclass(frozen=True)
class Rule:
    platform: str
    pattern: re.Pattern[str]
    page_offset: int = 0  # 文件名里的页码从 1 开始时设为 -1


@dataclass(frozen=True)
class RuleSet:
    platforms: frozenset[str]
    high: tuple[Rule, ...]


NO_MATCH = Recognition(Confidence.NONE)

_L = r"(?<![0-9A-Za-z])"  # 左边界：前面不是字母数字
_R = r"(?![0-9A-Za-z])"  # 右边界：后面不是字母数字

# Pixiv 作品 ID 的合理范围：8 位（2010 年起），或 1 开头的 9 位（截至 2026 年约 1.4 亿）。
# 7 位及以下太老、太容易和别的数字撞；10 位多为 Unix 时间戳。Pixiv 进入 2 开头的 9 位后需放宽。
PIXIV_ID = r"(?:[1-9]\d{7}|1\d{8})"
# X 的推文 ID（snowflake）：2011 年后为 17–19 位。15–16 位的多是其他 App 导出的时间戳。
X_ID = r"\d{17,20}"

# 本程序生成的文件名。platform 必须是已登记的平台 id 才算数。
OWN_FORMAT = re.compile(
    r"^(?P<platform>[a-z0-9-]+)_(?P<post_id>[0-9A-Za-z-]+)_p(?P<page>\d+)(?:_.*)?$"
)

# 内置补充的高置信规则（不属于某个平台的"自定义"，所以不放进 platform 表）
BUILTIN_HIGH: tuple[Rule, ...] = (
    # Pixiv 单页作品另存时的 "标题_ID"（多页作品是 "标题_ID_pN"，由 platform 表规则处理）
    Rule("pixiv", re.compile(rf"_(?P<post_id>{PIXIV_ID})$")),
    # gallery-dl 下载 X 的默认文件名 {tweet_id}_{num}，num 从 1 开始
    Rule("x", re.compile(rf"^(?P<post_id>{X_ID})_(?P<page>\d{{1,2}})$"), page_offset=-1),
)

# 中置信：文件名里孤立的一串数字
MEDIUM: tuple[Rule, ...] = (
    Rule("x", re.compile(rf"{_L}(?P<post_id>{X_ID}){_R}")),
    Rule("pixiv", re.compile(rf"{_L}(?P<post_id>{PIXIV_ID}){_R}")),
)

# X 网页右键保存的文件名是 15 位 media key（如 `EO2cBcJWoAAJJWf`），反推不出推文，
# 只能提示"大概来自 X"，post_id 留空，等用户贴链接。要求大小写字母混合，减少误判。
X_MEDIA_KEY = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])[A-Za-z0-9_-]{15}$")

# 8 位且形如 20YYMMDD 的数字多半是日期（截图、相机文件名），不作为 Pixiv ID
_DATE_LIKE = re.compile(r"^20\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])$")


def load_rules(conn: sqlite3.Connection) -> RuleSet:
    """从数据库的 platform 表读取规则。"""
    platforms: set[str] = set()
    high: list[Rule] = []
    for row in conn.execute("SELECT id, file_regex FROM platform ORDER BY rowid"):
        platforms.add(row["id"])
        if row["file_regex"]:
            high.append(Rule(row["id"], re.compile(row["file_regex"])))
    return RuleSet(frozenset(platforms), tuple(high))


def _from_match(rule: Rule, m: re.Match[str], confidence: Confidence) -> Recognition:
    groups = m.groupdict()
    page = int(groups["page"]) + rule.page_offset if groups.get("page") else 0
    return Recognition(confidence, rule.platform, groups["post_id"], max(page, 0))


def _plausible(rule: Rule, post_id: str) -> bool:
    return not (rule.platform == "pixiv" and _DATE_LIKE.match(post_id))


def recognize(stem: str, rules: RuleSet) -> Recognition:
    """识别文件名（不含扩展名）对应的来源。"""
    m = OWN_FORMAT.match(stem)
    if m and m["platform"] in rules.platforms:
        return Recognition(Confidence.HIGH, m["platform"], m["post_id"], int(m["page"]))

    for rule in (*rules.high, *BUILTIN_HIGH):
        if rule.platform not in rules.platforms:
            continue
        m = rule.pattern.search(stem)
        if m and _plausible(rule, m["post_id"]):
            return _from_match(rule, m, Confidence.HIGH)

    for rule in MEDIUM:
        if rule.platform not in rules.platforms:
            continue
        for m in rule.pattern.finditer(stem):
            if _plausible(rule, m["post_id"]):
                return _from_match(rule, m, Confidence.MEDIUM)

    if "x" in rules.platforms and X_MEDIA_KEY.match(stem):
        return Recognition(Confidence.MEDIUM, "x", None, None)

    return NO_MATCH
