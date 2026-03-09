"""记录转 DataFrame — 支持动态列"""

from __future__ import annotations

import pandas as pd


# 优先展示的列顺序（存在则靠前，不存在则跳过）
_PREFERRED_ORDER = [
    "title",
    "company",
    "location",
    "salary",
    "price",
    "source",
    "publish_date",
    "author",
    "authors",
    "snippet",
    "summary",
    "abstract",
    "content",
    "category",
    "priority",
    "city",
    "keywords",
    "ai_summary",
    "url",
    "error",
]


def records_to_dataframe(records: list[dict[str, str]]) -> pd.DataFrame:
    """
    将记录列表转换为 DataFrame，自动适配列。

    列顺序：优先按 _PREFERRED_ORDER 排列，其余列追加在后面。
    """
    dataframe = pd.DataFrame(records)
    if dataframe.empty:
        return pd.DataFrame(columns=["title", "content", "url"])

    # 按优先顺序排列列
    existing = [col for col in _PREFERRED_ORDER if col in dataframe.columns]
    remaining = [col for col in dataframe.columns if col not in existing]
    return dataframe[existing + remaining].fillna("").reset_index(drop=True)
