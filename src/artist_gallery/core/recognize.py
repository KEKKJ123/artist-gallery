"""从文件名识别作品来源。纯函数：输入文件名（不含扩展名）和规则，输出识别结果。

识别顺序（命中即停）：
1. 本程序自己生成的文件名 `{platform}_{post_id}_p{page}[_后缀]`  → 高置信
2. 各平台的文件名规则（内置见 platforms.py；自定义取 platform.file_regex）→ 高置信
3. 文件名里孤立的一串数字                                         → 中置信（进收件箱，附建议）
4. X 网页另存的 media key                                         → 中置信（只知道平台）
5. 都不匹配                                                       → 无（进收件箱）

"孤立"指数字两侧不是字母或数字：这样十六进制哈希（`1b82802012ab…`）、
`mmexport1738414323347` 之类不会被误认，而 `红豆_80742555`、`红豆123456789` 仍可识别。
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from enum import StrEnum

from artist_gallery.core.platforms import BUILTIN_BY_ID, PIXIV_ID, X_ID, Rule

log = logging.getLogger(__name__)
_A = re.ASCII


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
class RuleSet:
    platforms: frozenset[str]
    high: tuple[Rule, ...]


NO_MATCH = Recognition(Confidence.NONE)

_L = r"(?<![0-9A-Za-z])"  # 左边界：前面不是字母数字
_R = r"(?![0-9A-Za-z])"  # 右边界：后面不是字母数字

# 本程序生成的文件名。platform 必须是已登记的平台 id 才算数。
OWN_FORMAT = re.compile(
    r"^(?P<platform>[a-z0-9-]+)_(?P<post_id>[0-9A-Za-z-]+)_p(?P<page>[0-9]+)(?:_.*)?$", _A
)

# 中置信：文件名里孤立的一串数字
MEDIUM: tuple[Rule, ...] = (
    Rule("x", re.compile(rf"{_L}(?P<post_id>{X_ID}){_R}", _A)),
    Rule("pixiv", re.compile(rf"{_L}(?P<post_id>{PIXIV_ID}){_R}", _A)),
)

# X 网页右键保存的文件名是 15 位 media key（如 `EO2cBcJWoAAJJWf`），反推不出推文，
# 只能提示"大概来自 X"，post_id 留空，等用户贴链接。要求大小写字母混合，减少误判。
X_MEDIA_KEY = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])[A-Za-z0-9_-]{15}$", _A)

# 文件名里出现这些字样时，末尾的 8–9 位数字更可能是 QQ 号 / 账号，而不是 Pixiv ID：
# 带 guarded 标记的规则命中后降为中置信，进收件箱等确认。不区分大小写。
# 英文词要求两侧不是字母（避免 guide、fluid 里的 uid）；不用单字"群"（会误伤"群像"这类常见标题）。
ACCOUNT_HINT = re.compile(
    r"(?<![a-z])(?:qq|uid|avatar|wechat|weixin)(?![a-z])|头像|頭像|微信|群号|群聊|账号|帳號|帐号",
    re.IGNORECASE,
)

# 8 位且形如 20YYMMDD 的数字多半是日期（截图、相机文件名），不作为 Pixiv ID
_DATE_LIKE = re.compile(r"^20[0-9]{2}(0[1-9]|1[0-2])(0[1-9]|[12][0-9]|3[01])$")


def load_rules(conn: sqlite3.Connection) -> RuleSet:
    """内置平台用代码里的规则；自定义平台用 platform 表的 file_regex。"""
    platforms: set[str] = set()
    high: list[Rule] = []
    for row in conn.execute("SELECT id, file_regex FROM platform ORDER BY builtin DESC, rowid"):
        pid = row["id"]
        platforms.add(pid)
        if pid in BUILTIN_BY_ID:
            high.extend(BUILTIN_BY_ID[pid].file_rules)
        elif row["file_regex"]:
            try:
                pattern = re.compile(row["file_regex"])
            except re.error as e:
                log.warning("平台 %s 的 file_regex 无效，已忽略：%s", pid, e)
                continue
            if "post_id" not in pattern.groupindex:
                log.warning("平台 %s 的 file_regex 缺少命名组 post_id，已忽略", pid)
                continue
            high.append(Rule(pid, pattern))
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

    for rule in rules.high:
        m = rule.pattern.search(stem)
        if m and _plausible(rule, m["post_id"]):
            downgrade = rule.guarded and ACCOUNT_HINT.search(stem[: m.start()])
            return _from_match(rule, m, Confidence.MEDIUM if downgrade else Confidence.HIGH)

    for rule in MEDIUM:
        if rule.platform not in rules.platforms:
            continue
        for m in rule.pattern.finditer(stem):
            if _plausible(rule, m["post_id"]):
                return _from_match(rule, m, Confidence.MEDIUM)

    if "x" in rules.platforms and X_MEDIA_KEY.match(stem):
        return Recognition(Confidence.MEDIUM, "x", None, None)

    return NO_MATCH
