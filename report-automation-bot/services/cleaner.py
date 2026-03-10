"""数据清洗 — 去重、空行清理、类型强转、数据质量摘要"""

from __future__ import annotations

import pandas as pd


def detect_numeric_columns(dataframe: pd.DataFrame) -> list[str]:
    """自动检测数值列（50% 以上可转数值即认定）"""
    numeric_cols: list[str] = []
    for col in dataframe.columns:
        if col == "__source_file":
            continue
        series = pd.to_numeric(dataframe[col], errors="coerce")
        if series.notna().sum() >= max(1, int(len(dataframe) * 0.5)):
            numeric_cols.append(col)
    return numeric_cols


def coerce_dataframe(
    dataframe: pd.DataFrame,
    date_column: str,
    numeric_columns: list[str],
    fill_strategy: str = "zero",
    dedup: bool = False,
) -> pd.DataFrame:
    """
    强制转换列类型并清洗。

    Parameters
    ----------
    fill_strategy : "zero" | "median" | "none" — 数值列缺失值填充策略
    dedup : 是否去重
    """
    df = dataframe.copy()
    df.columns = [str(c).strip() for c in df.columns]

    # 去除全空行/列
    df = df.dropna(how="all").dropna(axis=1, how="all")

    # 去重
    if dedup:
        df = df.drop_duplicates()

    # 日期转换
    if date_column in df.columns:
        # 先尝试标准解析
        df[date_column] = pd.to_datetime(df[date_column], errors="coerce")
        # 对失败的行尝试常见格式
        mask = df[date_column].isna()
        if mask.any():
            for fmt in ["%Y%m%d", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y", "%Y年%m月%d日"]:
                still_na = df[date_column].isna()
                if not still_na.any():
                    break
                df.loc[still_na, date_column] = pd.to_datetime(
                    df.loc[still_na, date_column].astype(str), format=fmt, errors="coerce"
                )

    # 数值转换 + 填充
    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            if fill_strategy == "zero":
                df[col] = df[col].fillna(0)
            elif fill_strategy == "median":
                df[col] = df[col].fillna(df[col].median())
            # "none" 不填充

    df = df.reset_index(drop=True)
    return df


def compute_data_quality(dataframe: pd.DataFrame, date_column: str = "") -> dict:
    """计算数据质量摘要"""
    total = len(dataframe)
    if total == 0:
        return {"total_rows": 0, "duplicate_rows": 0, "duplicate_rate": "0%",
                "missing_cells": 0, "missing_rate": "0%", "date_invalid_rows": 0}

    dup_count = int(dataframe.duplicated().sum())
    total_cells = total * len(dataframe.columns)
    missing_cells = int(dataframe.isna().sum().sum())

    date_invalid = 0
    if date_column and date_column in dataframe.columns:
        date_invalid = int(dataframe[date_column].isna().sum())

    return {
        "total_rows": total,
        "duplicate_rows": dup_count,
        "duplicate_rate": f"{dup_count / total * 100:.1f}%",
        "missing_cells": missing_cells,
        "missing_rate": f"{missing_cells / total_cells * 100:.1f}%" if total_cells > 0 else "0%",
        "date_invalid_rows": date_invalid,
    }


def clip_outliers(df: pd.DataFrame, columns: list[str], method: str = "iqr") -> pd.DataFrame:
    """异常值裁剪。method: 'iqr' 或 'zscore'"""
    result = df.copy()
    for col in columns:
        if col not in result.columns:
            continue
        s = pd.to_numeric(result[col], errors="coerce")
        if method == "iqr":
            q1, q3 = s.quantile(0.25), s.quantile(0.75)
            iqr = q3 - q1
            lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            result[col] = s.clip(lower, upper)
        elif method == "zscore":
            mean, std = s.mean(), s.std()
            if std > 0:
                result[col] = s.clip(mean - 3 * std, mean + 3 * std)
    return result
