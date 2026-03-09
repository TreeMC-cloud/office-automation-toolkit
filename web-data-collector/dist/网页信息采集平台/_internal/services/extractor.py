from __future__ import annotations

import pandas as pd


def records_to_dataframe(records: list[dict[str, str]]) -> pd.DataFrame:
    dataframe = pd.DataFrame(records)
    if dataframe.empty:
        return pd.DataFrame(
            columns=[
                "title",
                "company",
                "location",
                "publish_date",
                "summary",
                "content",
                "category",
                "priority",
                "keywords",
                "ai_summary",
                "url",
                "error",
            ]
        )
    ordered_columns = [
        "title",
        "company",
        "location",
        "publish_date",
        "summary",
        "content",
        "category",
        "priority",
        "keywords",
        "ai_summary",
        "url",
        "error",
    ]
    existing = [column for column in ordered_columns if column in dataframe.columns]
    remaining = [column for column in dataframe.columns if column not in existing]
    return dataframe[existing + remaining].fillna("").reset_index(drop=True)
