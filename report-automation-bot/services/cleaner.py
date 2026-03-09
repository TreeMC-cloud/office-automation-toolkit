from __future__ import annotations

import pandas as pd


def detect_numeric_columns(dataframe: pd.DataFrame) -> list[str]:
    numeric_columns: list[str] = []
    for column in dataframe.columns:
        series = pd.to_numeric(dataframe[column], errors="coerce")
        if series.notna().sum() >= max(1, int(len(dataframe) * 0.5)):
            numeric_columns.append(column)
    return numeric_columns


def coerce_dataframe(dataframe: pd.DataFrame, date_column: str, numeric_columns: list[str]) -> pd.DataFrame:
    result = dataframe.copy()
    result.columns = [str(column).strip() for column in result.columns]
    if date_column in result.columns:
        result[date_column] = pd.to_datetime(result[date_column], errors="coerce")
    for column in numeric_columns:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0)
    return result
