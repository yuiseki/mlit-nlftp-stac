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

# A caveat about *permission*, which withholds what the licence grants: N03's
# 「※本データを二次利用する場合には、国土地理院に申請等必要な場合があります。」
# is the case this is for. Caveats about accuracy and legal standing are not
# licence conditions and must not be read as ones: 「確認してください」 appears
# in nearly every KSJ disclaimer, and treating it as a condition withheld
# permission that A52 砂防指定地 actually grants.
# Phrases, not words. A52 砂防指定地 says 「申請資料や根拠を示す必要がある資料
# への利用はできません」, which is about what the data may be used for, while
# N03 says 「申請等必要な場合があります」, which is about needing permission
# first. Matching the bare word 申請 confuses the two.
_CAVEATS = (
    "申請等必要", "申請が必要", "申請を要", "承諾を得", "許諾を得",
    "連絡を行う", "商用利用希望",
)

# 一部制限 means the conditions belong to whoever supplied the data, and the
# page lists them by prefecture. Where it does, an Item that knows its own
# prefecture can be resolved after all.
_OPEN_HEADING = re.compile(r"[＜<].*利用可.*再配信可.*[＞>]")
_ANY_HEADING = re.compile(r"^[＜<].+[＞>]$")


def _licence_of(text: str, region: Optional[str] = None) -> Tuple[str, str]:
    """(spdx, redistribution) for a chunk of terms with no year scoping."""
    if _RESTRICTED in text:
        if region and region in open_prefectures(text):
            return "CC-BY-4.0", ALLOWED
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
        # ＜…＞ on its own line, or ■… at the start of one: A31a heads its
        # year groups with ■2025年度、2024年度… and the licence follows below.
        m = re.match(r"^[＜<](.+?)[＞>]$", line) or re.match(r"^■\s*(.+)$", line)
        # A ＜＞ heading scopes what follows only when it names years. The same
        # bracket is used to group prefectures (＜オープンデータとしての利用可＞),
        # and reading that as a year scope leaves every rule yearless and the
        # whole statement unresolvable.
        if m and not _years_in(m.group(1))[0]:
            m = None
        if m:
            if current_scope is not None:
                out.append((current_scope, "\n".join(current)))
            current_scope, current = m.group(1), []
            continue
        # A line that is nothing but years is a heading as well. P11 writes
        # 「2022年度（令和4年度）」 on its own line with the licence underneath,
        # no bracket and no colon.
        years, _ = _years_in(line)
        if years and not re.sub(r"[0-9０-９年度（）()、,\s令和平成昭和元]", "", line):
            if current_scope is not None:
                out.append((current_scope, "\n".join(current)))
            current_scope, current = line, []
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


def _normalise_pref(name: str) -> str:
    return re.sub(r"[都道府県]$", "", name.strip()) if name.strip() != "北海道" else "北海道"


def open_prefectures(terms: str) -> List[str]:
    """The prefectures a 一部制限 page names as free to redistribute."""
    lines = terms.splitlines()
    out: List[str] = []
    collecting = False
    for line in lines:
        line = line.strip()
        if _OPEN_HEADING.search(line):
            collecting = True
            continue
        if collecting:
            if _ANY_HEADING.match(line) or line.startswith(("■", "【", "・")):
                break
            out += [_normalise_pref(p) for p in re.split(r"[、,]", line) if p.strip()]
    return [p for p in out if p]


def resolve(terms: str, year: Optional[int], region: Optional[str] = None) -> Tuple[str, str, str]:
    """(spdx, redistribution, the wording this came from).

    `year` is the Item's year; without one, terms that vary by year cannot be
    resolved. `region` is the Item's 地域, which resolves a 一部制限 page that
    lists its prefectures.
    """
    terms = (terms or "").strip()
    if not terms:
        return "other", CHECK, ""

    rules = _rules(terms)
    scoped = [(s, b) for s, b in rules if s]
    if not scoped:
        spdx, redis = _licence_of(terms, region)
        # The line that states the licence, not the whole statement. Several
        # pages append 座標系 and its value to the same field, and returning
        # all of it made "the sentence that decided" include the CRS.
        deciding = next(
            (ln.strip() for ln in terms.splitlines()
             if ln.strip() and _licence_of(ln)[0:2] != ("other", CHECK)),
            terms.splitlines()[0].strip(),
        )
        return spdx, redis, deciding

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
            spdx, redis = _licence_of(body, region)
            return spdx, redis, f"{scope}：{body.splitlines()[0]}"
    if fallback is not None:
        spdx, redis = _licence_of(fallback, region)
        return spdx, redis, f"上記以外：{fallback.splitlines()[0]}"
    return "other", CHECK, terms
