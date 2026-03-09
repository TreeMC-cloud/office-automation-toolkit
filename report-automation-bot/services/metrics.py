"""指标计算 — 多聚合方式、环比、趋势判断、异常检测"""

from __future__ import annotations

import numpy as np
import pandas as pd

AGG_FUNCS = {
    "求和": "sum",
    "计数": "count",
    "均值": "mean",
    "中位数": "median",
    "最小值": "min",
    "最大值": "max",
}


def compute_overview(
    dataframe: pd.DataFrame, date_column: str, value_column: str,
) -> dict:
    """计算总览指标（含 max/min/std）"""
    n = len(dataframe)
    if n == 0:
        return _empty_overview()

    col = dataframe[value_column]
    total = round(float(col.sum()), 2)
    avg = round(float(col.mean()), 2)
    med = round(float(col.median()), 2)
    max_val = round(float(col.max()), 2)
    min_val = round(float(col.min()), 2)
    std_val = round(float(col.std()), 2) if n > 1 else 0.0

    latest_label, latest_val = "未识别", 0.0
    if dataframe[date_column].notna().any():
        latest = dataframe[date_column].max().normalize()
        latest_val = round(float(
            dataframe.loc[dataframe[date_column].dt.normalize() == latest, value_column].sum()
        ), 2)
        latest_label = latest.strftime("%Y-%m-%d")

    return {
        "total_records": n,
        "total_value": total,
        "average_value": avg,
        "median_value": med,
        "max_value": max_val,
        "min_value": min_val,
        "std_value": std_val,
        "latest_period": latest_label,
        "latest_period_value": latest_val,
    }


def aggregate_by_period(
    dataframe: pd.DataFrame,
    date_column: str,
    value_column: str,
    freq: str = "D",
    agg: str = "sum",
) -> pd.DataFrame:
    """按时间粒度聚合 + 环比计算"""
    valid = dataframe.dropna(subset=[date_column]).copy()
    if valid.empty:
        return pd.DataFrame(columns=["period", value_column, "环比变化率"])

    agg_func = agg if agg in ("sum", "count", "mean", "median", "min", "max") else "sum"
    grouped = (
        valid.set_index(date_column)[value_column]
        .resample(freq)
        .agg(agg_func)
        .reset_index()
    )
    grouped.columns = ["period", value_column]

    # 环比变化率
    grouped["环比变化率"] = grouped[value_column].pct_change() * 100
    grouped["环比变化率"] = grouped["环比变化率"].round(2)

    grouped["period"] = grouped["period"].dt.strftime("%Y-%m-%d")
    return grouped


def aggregate_by_dimension(
    dataframe: pd.DataFrame,
    dimension_column: str | None,
    value_column: str,
    top_n: int = 5,
    agg: str = "sum",
) -> pd.DataFrame:
    """按维度聚合 Top N + 其他汇总"""
    if not dimension_column or dimension_column not in dataframe.columns:
        return pd.DataFrame(columns=["dimension", value_column, "占比"])

    agg_func = agg if agg in ("sum", "count", "mean", "median", "min", "max") else "sum"
    grouped = (
        dataframe.groupby(dimension_column, dropna=False)[value_column]
        .agg(agg_func)
        .reset_index()
        .sort_values(by=value_column, ascending=False)
    )
    grouped.columns = [dimension_column, value_column]

    total = grouped[value_column].sum()

    top = grouped.head(top_n).copy()
    rest = grouped.iloc[top_n:]

    # 占比
    top["占比"] = (top[value_column] / total * 100).round(1).astype(str) + "%"

    # 其他汇总行
    if not rest.empty:
        rest_sum = rest[value_column].sum()
        rest_pct = f"{rest_sum / total * 100:.1f}%" if total > 0 else "0%"
        other_row = pd.DataFrame({
            dimension_column: ["其他"],
            value_column: [round(rest_sum, 2)],
            "占比": [rest_pct],
        })
        top = pd.concat([top, other_row], ignore_index=True)

    return top.reset_index(drop=True)


def detect_trend(trend_df: pd.DataFrame, value_column: str) -> dict:
    """检测趋势方向和异常波动"""
    if len(trend_df) < 2:
        return {"direction": "数据不足", "consecutive": 0, "anomalies": []}

    values = trend_df[value_column].tolist()
    periods = trend_df["period"].tolist()

    # 连续上升/下降
    direction, consecutive = _detect_consecutive(values)

    # 异常检测（±2σ）
    arr = np.array(values, dtype=float)
    mean, std = arr.mean(), arr.std()
    anomalies = []
    if std > 0:
        for i, (v, p) in enumerate(zip(values, periods)):
            z = (v - mean) / std
            if abs(z) > 2:
                label = "异常高" if z > 0 else "异常低"
                anomalies.append({"period": p, "value": v, "label": label, "z_score": round(z, 2)})

    return {
        "direction": direction,
        "consecutive": consecutive,
        "anomalies": anomalies,
    }


def _detect_consecutive(values: list) -> tuple[str, int]:
    """检测连续上升/下降"""
    if len(values) < 2:
        return "数据不足", 0

    up_count, down_count = 0, 0
    for i in range(len(values) - 1, 0, -1):
        if values[i] > values[i - 1]:
            up_count += 1
        else:
            break
    for i in range(len(values) - 1, 0, -1):
        if values[i] < values[i - 1]:
            down_count += 1
        else:
            break

    if up_count >= 3:
        return f"连续上升 {up_count} 期", up_count
    if down_count >= 3:
        return f"连续下降 {down_count} 期", down_count
    if up_count > 0:
        return "近期上升", up_count
    if down_count > 0:
        return "近期下降", down_count
    return "持平", 0


def _empty_overview() -> dict:
    return {
        "total_records": 0, "total_value": 0.0, "average_value": 0.0,
        "median_value": 0.0, "max_value": 0.0, "min_value": 0.0, "std_value": 0.0,
        "latest_period": "未识别", "latest_period_value": 0.0,
    }
