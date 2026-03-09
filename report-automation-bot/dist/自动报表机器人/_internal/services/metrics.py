from __future__ import annotations

import pandas as pd


def compute_overview(dataframe: pd.DataFrame, date_column: str, value_column: str) -> dict[str, object]:
    total_records = int(len(dataframe))
    total_value = round(float(dataframe[value_column].sum()), 2) if total_records else 0.0
    average_value = round(float(dataframe[value_column].mean()), 2) if total_records else 0.0

    if total_records and dataframe[date_column].notna().any():
        latest_period = dataframe[date_column].max().normalize()
        latest_period_value = round(
            float(dataframe.loc[dataframe[date_column].dt.normalize() == latest_period, value_column].sum()), 2
        )
        latest_period_label = latest_period.strftime("%Y-%m-%d")
    else:
        latest_period_value = 0.0
        latest_period_label = "未识别"

    return {
        "total_records": total_records,
        "total_value": total_value,
        "average_value": average_value,
        "latest_period": latest_period_label,
        "latest_period_value": latest_period_value,
    }


def aggregate_by_period(dataframe: pd.DataFrame, date_column: str, value_column: str, freq: str = "D") -> pd.DataFrame:
    valid = dataframe.dropna(subset=[date_column]).copy()
    if valid.empty:
        return pd.DataFrame(columns=["period", value_column])
    grouped = valid.set_index(date_column)[value_column].resample(freq).sum().reset_index()
    grouped.columns = ["period", value_column]
    grouped["period"] = grouped["period"].dt.strftime("%Y-%m-%d")
    return grouped


def aggregate_by_dimension(
    dataframe: pd.DataFrame,
    dimension_column: str | None,
    value_column: str,
    top_n: int = 5,
) -> pd.DataFrame:
    if not dimension_column or dimension_column not in dataframe.columns:
        return pd.DataFrame(columns=["dimension", value_column])
    grouped = (
        dataframe.groupby(dimension_column, dropna=False)[value_column]
        .sum()
        .reset_index()
        .sort_values(by=value_column, ascending=False)
        .head(top_n)
    )
    grouped.columns = [dimension_column, value_column]
    return grouped.reset_index(drop=True)
