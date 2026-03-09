"""文本标准化工具 — Unicode 归一化、全角转半角、公司名后缀剥离"""

from __future__ import annotations

import re
import unicodedata


def normalize_text(text: str) -> str:
    """NFKC 归一化 + 全角转半角 + 去除多余空白"""
    if not isinstance(text, str):
        text = str(text)
    text = unicodedata.normalize("NFKC", text)
    text = _fullwidth_to_halfwidth(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_column_name(name: str) -> str:
    """列名标准化：小写 + 去空白 + 去下划线"""
    return normalize_text(name).lower().replace("_", "").replace(" ", "")


# ---------------------------------------------------------------------------
# 公司名标准化
# ---------------------------------------------------------------------------

_CN_SUFFIXES = [
    "股份有限公司", "有限责任公司", "有限公司", "责任公司",
    "集团公司", "集团", "总公司", "分公司",
]

_EN_SUFFIXES = [
    "corporation", "incorporated", "limited",
    "company", "corp.", "corp", "inc.", "inc",
    "ltd.", "ltd", "llc", "l.l.c.", "co.", "co",
    "plc", "gmbh", "ag", "s.a.", "sa",
]

_EN_SUFFIX_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(s) for s in _EN_SUFFIXES) + r")\s*$",
    re.IGNORECASE,
)


def normalize_company_name(name: str) -> str:
    """公司名标准化：去除中英文后缀、括号内容、标点"""
    text = normalize_text(name)

    # 去除括号及其内容（中英文括号）
    text = re.sub(r"[（(][^）)]*[）)]", "", text)

    # 循环剥离中文后缀
    changed = True
    while changed:
        changed = False
        for suffix in _CN_SUFFIXES:
            if text.endswith(suffix):
                text = text[: -len(suffix)]
                changed = True
                break

    # 剥离英文后缀
    text = _EN_SUFFIX_PATTERN.sub("", text)

    # 去除尾部标点
    text = re.sub(r"[,，.。、\s]+$", "", text)
    return text.strip()


# ---------------------------------------------------------------------------
# 全角 → 半角
# ---------------------------------------------------------------------------

def _fullwidth_to_halfwidth(text: str) -> str:
    """将全角字符转为半角（数字、字母、常见标点）"""
    result = []
    for ch in text:
        code = ord(ch)
        # 全角空格
        if code == 0x3000:
            result.append(" ")
        # 全角 ! ~ 范围 → 半角
        elif 0xFF01 <= code <= 0xFF5E:
            result.append(chr(code - 0xFEE0))
        else:
            result.append(ch)
    return "".join(result)


def smart_normalize_key(value, is_numeric_col: bool = False) -> str:
    """智能主键标准化：数字型保留精度，文本型走公司名清洗"""
    if value is None or (isinstance(value, float) and value != value):  # NaN
        return ""
    if is_numeric_col:
        # 数字型：去除尾部 .0，保留原始精度
        s = str(value).strip()
        if s.endswith(".0"):
            s = s[:-2]
        return s
    return normalize_company_name(str(value))
