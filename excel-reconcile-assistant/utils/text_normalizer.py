from __future__ import annotations

import re
import unicodedata


COMPANY_SUFFIXES = [
    "股份有限公司",
    "有限责任公司",
    "有限公司",
    "集团有限公司",
    "集团",
    "公司",
]


def normalize_text(value) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\s+", "", text)
    return text.strip()


def normalize_column_name(value) -> str:
    text = normalize_text(value).lower()
    return re.sub(r"[^\w一-鿿]", "", text)


def normalize_company_name(value) -> str:
    text = normalize_text(value)
    for suffix in COMPANY_SUFFIXES:
        if text.endswith(suffix):
            text = text[: -len(suffix)]
            break
    text = re.sub(r"[()（）\-—_·,，.。]", "", text)
    return text.lower()
