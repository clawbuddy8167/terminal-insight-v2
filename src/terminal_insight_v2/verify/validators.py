"""Field validators used by Verify."""
from __future__ import annotations

import re
from typing import Callable, Dict, List, Tuple

ValidatorFn = Callable[[str], Tuple[bool, str]]

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$|^\d{4}年\d{1,2}月")
_DIGIT = re.compile(r"\d")
_IP = re.compile(r"\bIP\s?\d{2}\b", re.I)
_MAH = re.compile(r"\d+\s*mAh", re.I)
_WATT = re.compile(r"\d+(\.\d+)?\s*W\b", re.I)
_WEIGHT = re.compile(r"\d+(\.\d+)?\s*g\b", re.I)
_YES_NO = re.compile(r"^(是|否|支持|不支持|有|无)")
_WATCH_WATER = re.compile(r"(ATM|IP\s?\d{2}|米|m\b)", re.I)
_WATCH_SIZE = re.compile(r"\d+(\.\d+)?\s*(mm|毫米)", re.I)


def _ok(msg: str = "ok") -> Tuple[bool, str]:
    return True, msg


def _bad(msg: str) -> Tuple[bool, str]:
    return False, msg


VALIDATORS: Dict[str, ValidatorFn] = {
    "non_empty": lambda v: _ok() if (v or "").strip() else _bad("empty"),
    "date_iso": lambda v: _ok() if _DATE.search(v or "") else _bad("not_date"),
    "has_digit": lambda v: _ok() if _DIGIT.search(v or "") else _bad("no_digit"),
    "ip_rating": lambda v: _ok() if _IP.search(v or "") else _bad("no_ip"),
    "mah": lambda v: _ok() if _MAH.search(v or "") else _bad("no_mah"),
    "watt": lambda v: _ok() if _WATT.search(v or "") else _bad("no_watt"),
    "weight_g": lambda v: _ok() if _WEIGHT.search(v or "") else _bad("no_weight_g"),
    "yes_no_zh": lambda v: _ok() if _YES_NO.search((v or "").strip()) else _bad("not_yes_no"),
    "watch_water": lambda v: _ok() if _WATCH_WATER.search(v or "") else _bad("no_water"),
    "watch_battery": lambda v: _ok() if (_DIGIT.search(v or "") and ("天" in (v or "") or "小时" in (v or "") or "h" in (v or "").lower() or "mAh" in (v or ""))) else _bad("no_battery"),
    "watch_size": lambda v: _ok() if _WATCH_SIZE.search(v or "") else _bad("no_size"),
    "storage_combo": lambda v: _ok() if _DIGIT.search(v or "") else _bad("no_storage"),
    "screen_token": lambda v: _ok() if (v or "").strip() else _bad("empty_screen"),
}


def run_validators(value: str, names: List[str]) -> Tuple[bool, str]:
    if not names:
        return True, "no_validators"
    notes: List[str] = []
    for name in names:
        fn = VALIDATORS.get(name)
        if not fn:
            notes.append(f"{name}:unknown")
            continue
        ok, reason = fn(value)
        notes.append(f"{name}:{reason}")
        if not ok:
            return False, ";".join(notes)
    return True, ";".join(notes)


def snippet_supports_value(snippet: str, value: str) -> Tuple[bool, str]:
    """Heuristic evidence check: snippet should share digits or significant chars with value."""
    sn = (snippet or "").strip()
    val = (value or "").strip()
    if not sn or not val:
        return False, "empty_snippet_or_value"
    # exact containment
    if val in sn or sn in val:
        return True, "contains"
    # digit overlap
    digits_v = set(re.findall(r"\d+", val))
    digits_s = set(re.findall(r"\d+", sn))
    if digits_v and digits_v & digits_s:
        return True, "digit_overlap"
    # token overlap (CJK 2+ chars or latin word)
    tokens = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z]{3,}", val)
    hits = [t for t in tokens if t.lower() in sn.lower()]
    if hits:
        return True, f"token:{hits[0]}"
    return False, "no_overlap"
