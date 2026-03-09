"""重复记录检测 — 支持多列组合查重，返回频次和组号"""

from __future__ import annotations

import pandas as pd


def find_duplicates(
    df: pd.DataFrame,
    key_columns: str | list[str],
) -> pd.DataFrame:
    """
    检测重复记录。

    Parameters
    ----------
    key_columns : 单列名或多列名列表

    Returns
    -------
    DataFrame 包含所有重复行，附加 "重复次数" 和 "重复组号" 列
    """
    if df.empty:
        return pd.DataFrame()

    cols = [key_columns] if isinstance(key_columns, str) else list(key_columns)

    # 找出重复的行（keep=False 保留所有重复项）
    dup_mask = df.duplicated(subset=cols, keep=False)
    if not dup_mask.any():
        return pd.DataFrame()

    result = df[dup_mask].copy()

    # 计算每个重复值的出现次数
    count_map = df.groupby(cols).size()
    result["重复次数"] = result.apply(
        lambda row: count_map.loc[tuple(row[c] for c in cols)] if len(cols) > 1
        else count_map.loc[row[cols[0]]],
        axis=1,
    )

    # 分配重复组号
    group_keys = result[cols].drop_duplicates()
    group_keys = group_keys.reset_index(drop=True)
    group_keys["重复组号"] = range(1, len(group_keys) + 1)

    result = result.merge(group_keys, on=cols, how="left")

    # 排序：按组号、原始顺序
    result = result.sort_values(["重复组号"] + cols).reset_index(drop=True)

    return result
