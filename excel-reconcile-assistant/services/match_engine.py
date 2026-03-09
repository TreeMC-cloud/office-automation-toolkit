"""核对引擎 — 复合主键、向量化比对、数值容差、智能类型判断"""

from __future__ import annotations

import pandas as pd
import numpy as np

from utils.text_normalizer import normalize_text, smart_normalize_key


def reconcile_dataframes(
    df_left: pd.DataFrame,
    df_right: pd.DataFrame,
    key_left: str | list[str],
    key_right: str | list[str],
    compare_pairs: list[tuple[str, str]],
    tolerance: float = 0.0,
) -> dict:
    """
    核对两个 DataFrame。

    Parameters
    ----------
    key_left / key_right : 主键列名，支持单列字符串或多列列表（复合主键）
    compare_pairs : [(left_col, right_col), ...] 需要比对的字段对
    tolerance : 数值容差，差值 <= tolerance 视为一致

    Returns
    -------
    dict with keys: matched_records, exact_matches, missing_in_b, missing_in_a,
                    mismatch_details, stats
    """
    # 统一为列表
    keys_l = [key_left] if isinstance(key_left, str) else list(key_left)
    keys_r = [key_right] if isinstance(key_right, str) else list(key_right)

    if len(keys_l) != len(keys_r):
        raise ValueError("左右主键列数量必须一致")

    left = df_left.copy()
    right = df_right.copy()

    # 构建合并用的标准化主键
    merge_key = "_merge_key_"
    left[merge_key] = _build_composite_key(left, keys_l)
    right[merge_key] = _build_composite_key(right, keys_r)

    # 外连接
    merged = pd.merge(
        left, right,
        on=merge_key, how="outer",
        suffixes=("_A", "_B"),
        indicator=True,
    )

    # 分类
    matched = merged[merged["_merge"] == "both"].copy()
    missing_in_b = merged[merged["_merge"] == "left_only"].copy()  # A 有 B 无
    missing_in_a = merged[merged["_merge"] == "right_only"].copy()  # B 有 A 无

    # 清理辅助列
    for df_tmp in [matched, missing_in_b, missing_in_a]:
        df_tmp.drop(columns=[merge_key, "_merge"], inplace=True, errors="ignore")

    # 向量化字段比对
    exact_mask = pd.Series(True, index=matched.index)
    mismatch_rows = []

    for col_l, col_r in compare_pairs:
        # 确定合并后的实际列名
        actual_l = _resolve_merged_col(col_l, matched.columns, "_A")
        actual_r = _resolve_merged_col(col_r, matched.columns, "_B")

        if actual_l is None or actual_r is None:
            continue

        vals_l = matched[actual_l]
        vals_r = matched[actual_r]

        # 向量化比较
        is_match = _vectorized_compare(vals_l, vals_r, tolerance)
        exact_mask &= is_match

        # 收集不一致的行
        diff_idx = matched.index[~is_match]
        for idx in diff_idx:
            v_l = vals_l.loc[idx]
            v_r = vals_r.loc[idx]
            # 判断差异类型
            diff_type = _classify_diff(v_l, v_r)

            # 获取主键值用于定位
            key_vals = []
            for kl in keys_l:
                actual_kl = _resolve_merged_col(kl, matched.columns, "_A")
                key_vals.append(str(matched.loc[idx, actual_kl]) if actual_kl else "")

            mismatch_rows.append({
                "主键值": " | ".join(key_vals),
                "字段A": col_l,
                "A值": _safe_str(v_l),
                "字段B": col_r,
                "B值": _safe_str(v_r),
                "差异类型": diff_type,
            })

    exact_matches = matched[exact_mask].copy()
    mismatch_details = pd.DataFrame(mismatch_rows) if mismatch_rows else pd.DataFrame(
        columns=["主键值", "字段A", "A值", "字段B", "B值", "差异类型"]
    )

    # 清理 missing 表的辅助后缀列，只保留有意义的列
    missing_in_b = _clean_missing_df(missing_in_b, "_A")
    missing_in_a = _clean_missing_df(missing_in_a, "_B")

    total_left = len(df_left)
    total_right = len(df_right)
    matched_count = len(matched)
    exact_count = len(exact_matches)

    stats = {
        "left_rows": total_left,
        "right_rows": total_right,
        "matched_rows": matched_count,
        "exact_match_rows": exact_count,
        "mismatch_rows": matched_count - exact_count,
        "missing_in_b_rows": len(missing_in_b),
        "missing_in_a_rows": len(missing_in_a),
        "match_rate": f"{matched_count / total_left * 100:.1f}%" if total_left > 0 else "0%",
        "exact_rate": f"{exact_count / matched_count * 100:.1f}%" if matched_count > 0 else "0%",
    }

    return {
        "matched_records": matched.drop(columns=[merge_key], errors="ignore"),
        "exact_matches": exact_matches.drop(columns=[merge_key], errors="ignore"),
        "missing_in_b": missing_in_b,
        "missing_in_a": missing_in_a,
        "mismatch_details": mismatch_details,
        "stats": stats,
    }


# ---------------------------------------------------------------------------
# 内部函数
# ---------------------------------------------------------------------------

def _build_composite_key(df: pd.DataFrame, key_cols: list[str]) -> pd.Series:
    """构建复合主键，智能判断列类型"""
    parts = []
    for col in key_cols:
        is_numeric = pd.api.types.is_numeric_dtype(df[col])
        parts.append(df[col].apply(lambda v: smart_normalize_key(v, is_numeric)))
    if len(parts) == 1:
        return parts[0]
    return parts[0].str.cat(parts[1:], sep="||")


def _resolve_merged_col(original: str, columns: pd.Index, suffix: str) -> str | None:
    """解析合并后的列名（可能带 _A/_B 后缀）"""
    if original in columns:
        return original
    with_suffix = original + suffix
    if with_suffix in columns:
        return with_suffix
    return None


def _vectorized_compare(s1: pd.Series, s2: pd.Series, tolerance: float) -> pd.Series:
    """向量化比较两列，支持数值容差和 NaN 处理"""
    # 两边都是 NaN → 视为一致
    both_nan = s1.isna() & s2.isna()

    # 一边 NaN → 不一致
    one_nan = s1.isna() ^ s2.isna()

    # 尝试数值比较
    if tolerance > 0:
        n1 = pd.to_numeric(s1, errors="coerce")
        n2 = pd.to_numeric(s2, errors="coerce")
        both_numeric = n1.notna() & n2.notna()
        numeric_match = both_numeric & ((n1 - n2).abs() <= tolerance)
    else:
        numeric_match = pd.Series(False, index=s1.index)

    # 文本比较（标准化后）
    t1 = s1.astype(str).apply(normalize_text)
    t2 = s2.astype(str).apply(normalize_text)
    text_match = t1 == t2

    return both_nan | numeric_match | (~one_nan & text_match)


def _classify_diff(v1, v2) -> str:
    """分类差异类型"""
    if _is_nan(v1) and not _is_nan(v2):
        return "A为空"
    if not _is_nan(v1) and _is_nan(v2):
        return "B为空"
    if _is_nan(v1) and _is_nan(v2):
        return "双方为空"
    # 类型不同
    try:
        f1, f2 = float(v1), float(v2)
        return f"数值差异({abs(f1 - f2):.4g})"
    except (ValueError, TypeError):
        pass
    return "值不同"


def _is_nan(v) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and np.isnan(v):
        return True
    if isinstance(v, str) and v.strip() in ("", "nan", "NaN", "None"):
        return True
    return False


def _safe_str(v) -> str:
    if _is_nan(v):
        return "(空)"
    return str(v)


def _clean_missing_df(df: pd.DataFrame, keep_suffix: str) -> pd.DataFrame:
    """清理 missing DataFrame，去掉另一侧的空列"""
    drop_suffix = "_B" if keep_suffix == "_A" else "_A"
    cols_to_drop = [c for c in df.columns if c.endswith(drop_suffix)]
    df = df.drop(columns=cols_to_drop, errors="ignore")
    # 重命名：去掉保留侧的后缀
    rename_map = {c: c.replace(keep_suffix, "") for c in df.columns if c.endswith(keep_suffix)}
    return df.rename(columns=rename_map)
