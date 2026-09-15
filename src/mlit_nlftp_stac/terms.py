"""Resolving 使用許諾条件 for one year, and deciding what may be republished.

The licence of a KSJ dataset is not a property of the dataset. It is a
property of the year: 鉄道データ is CC BY 4.0 from 2020 and merely
"commercial use allowed" before that, 学校データ is CC BY 4.0 for 2023 and
2021 and non-commercial for 2013. A Collection holds every year, so a single
answer for the Collection is either wrong or useless. Items have years, so
Items are where this can be answered.

What "may be republished" means comes from the terms of use themselves
(https://nlftp.mlit.go.jp/ksj/other/agreement_02.html, 第1条):

    （ａ）「商用可」＝ ... 商用目的での利用（複製物の再配布を含む）が可能
    （ｂ）「非商用」＝ ... 非商用目的のみでの利用（ただし複製物の再配布を除く）

So 商用可 allows redistribution and 非商用 excludes it, in as many words.
Anything this module cannot resolve is reported as "check" rather than
guessed, because the cost of a wrong "allowed" is someone republishing data
they were not licensed to.
"""

import re
from typing import List, Optional, Tuple

ALLOWED = "allowed"
NOT_ALLOWED = "not-allowed"
CHECK = "check"

_CC = re.compile(r"CC[_ ]?BY[_ ]?4\.0", re.I)
_RESTRICTED = "一部制限"
_ERAS = {"令和": 2018, "平成": 1988, "昭和": 1925}

# A caveat that does not name a year but does mean the answer is not simply
# the licence: N03 is CC BY 4.0 「※本データを二次利用する場合には、国土地理院に
# 申請等必要な場合があります。」, which is exactly the case this is for.
_CAVEATS = ("申請", "承諾", "問い合わせ", "連絡を行う", "遵守すること", "確認してください")


def _licence_of(text: str) -> Tuple[str, str]:
    """(spdx, redistribution) for a chunk of terms with no year scoping."""
    if _RESTRICTED in text:
        return "other", CHECK
    if _CC.search(text):
        if any(c in text for c in _CAVEATS):
            return "other", CHECK
        return "CC-BY-4.0", ALLOWED
    if "非商用" in text:
        return "other", NOT_ALLOWED
    if "商用可" in text:
        return "other", ALLOWED
    return "other", CHECK


def _years_in(scope: str) -> Tuple[List[int], bool]:
    """The years a scope names, and whether it means "and later"."""
    years = [int(y) for y in re.findall(r"((?:19|20)\d{2})\s*年", scope)]
    for era, base in _ERAS.items():
        for n in re.findall(rf"{era}\s*(元|\d+)\s*年", scope):
            years.append(base + (1 if n == "元" else int(n)))
    return sorted(set(years)), "以降" in scope


def _rules(terms: str) -> List[Tuple[str, str]]:
    """[(scope, body)] in the order the page states them."""
    out: List[Tuple[str, str]] = []
    current_scope = None
    current: List[str] = []
    for line in terms.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^[＜<](.+?)[＞>]$", line)
        if m:  # a heading that scopes the lines under it
            if current_scope is not None:
                out.append((current_scope, "\n".join(current)))
            current_scope, current = m.group(1), []
            continue
        m = re.match(r"^(.{2,40}?)[：:]\s*(.+)$", line)
        if m and (_years_in(m.group(1))[0] or "上記以外" in m.group(1)):
            if current_scope is not None:
                out.append((current_scope, "\n".join(current)))
                current_scope, current = None, []
            out.append((m.group(1), m.group(2)))
            continue
        if current_scope is not None:
            current.append(line)
        else:
            out.append(("", line))
    if current_scope is not None:
        out.append((current_scope, "\n".join(current)))
    return out


def resolve(terms: str, year: Optional[int]) -> Tuple[str, str, str]:
    """(spdx, redistribution, the wording this came from).

    `year` is the Item's year. Without one, terms that vary by year cannot be
    resolved and the answer is `check`.
    """
    terms = (terms or "").strip()
    if not terms:
        return "other", CHECK, ""

    rules = _rules(terms)
    scoped = [(s, b) for s, b in rules if s]
    if not scoped:
        spdx, redis = _licence_of(terms)
        return spdx, redis, terms

    if year is None:
        return "other", CHECK, terms

    fallback = None
    for scope, body in scoped:
        if "上記以外" in scope:
            fallback = body
            continue
        years, onward = _years_in(scope)
        if not years:
            continue
        if (onward and year >= min(years)) or (not onward and year in years):
            spdx, redis = _licence_of(body)
            return spdx, redis, f"{scope}：{body.splitlines()[0]}"
    if fallback is not None:
        spdx, redis = _licence_of(fallback)
        return spdx, redis, f"上記以外：{fallback.splitlines()[0]}"
    return "other", CHECK, terms
