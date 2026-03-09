"""记录转 DataFrame — 支持动态列，新增字段优先级"""

from __future__ import annotations

import pandas as pd


_PREFERRED_ORDER = [
    "title",
    "image_url",
    "image_urls",
    "brand",
    "price",
    "price_range",
    "specs",
    "company",
    "location",
    "salary",
    "source",
    "domain",
    "search_engine",
    "publish_date",
    "author",
    "authors",
    "snippet",
    "summary",
    "abstract",
    "content",
    "category",
    "priority",
    "sentiment",
    "city",
    "keywords",
    "ai_summary",
    "quality_score",
    "url",
    "error",
]


def records_to_dataframe(records: list[dict[str, str]]) -> pd.DataFrame:
    """将记录列表转换为 DataFrame，自动适配列并按优先级排序"""
    dataframe = pd.DataFrame(records)
    if dataframe.empty:
        return pd.DataFrame(columns=["title", "content", "url"])

    # 移除全空列
    dataframe = dataframe.loc[:, dataframe.fillna("").astype(str).apply(lambda c: c.str.strip()).ne("").any()]

    existing = [col for col in _PREFERRED_ORDER if col in dataframe.columns]
    remaining = [col for col in dataframe.columns if col not in existing]
    return dataframe[existing + remaining].fillna("").reset_index(drop=True)
