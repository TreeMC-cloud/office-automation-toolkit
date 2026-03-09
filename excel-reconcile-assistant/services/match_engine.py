    from __future__ import annotations

    import pandas as pd

    from utils.text_normalizer import normalize_company_name, normalize_text


    def _build_match_key(series: pd.Series) -> pd.Series:
        return series.fillna("").astype(str).map(normalize_company_name)


    def _resolve_value(row: pd.Series, column: str, side: str, left_columns: list[str], right_columns: list[str]):
        if column in left_columns and column in right_columns:
            suffix = "_a" if side == "a" else "_b"
            return row.get(f"{column}{suffix}", "")
        return row.get(column, "")


    def reconcile_dataframes(
        dataframe_a: pd.DataFrame,
        dataframe_b: pd.DataFrame,
        key_a: str,
        key_b: str,
        compare_pairs: list[tuple[str, str]],
    ) -> dict[str, pd.DataFrame | dict[str, int]]:
        left = dataframe_a.copy()
        right = dataframe_b.copy()

        left["__match_key"] = _build_match_key(left[key_a])
        right["__match_key"] = _build_match_key(right[key_b])
        left["__row_id_a"] = range(len(left))
        right["__row_id_b"] = range(len(right))

        merged = left.merge(right, on="__match_key", how="outer", suffixes=("_a", "_b"), indicator=True)
        left_columns = left.columns.tolist()
        right_columns = right.columns.tolist()

        matched_records = merged.loc[merged["_merge"] == "both"].drop(columns=["__match_key"]).reset_index(drop=True)
        missing_in_b_keys = merged.loc[merged["_merge"] == "left_only", "__match_key"].dropna().unique().tolist()
        missing_in_a_keys = merged.loc[merged["_merge"] == "right_only", "__match_key"].dropna().unique().tolist()

        missing_in_b = left.loc[left["__match_key"].isin(missing_in_b_keys)].drop(columns=["__match_key", "__row_id_a"]).reset_index(drop=True)
        missing_in_a = right.loc[right["__match_key"].isin(missing_in_a_keys)].drop(columns=["__match_key", "__row_id_b"]).reset_index(drop=True)

        mismatch_records: list[dict[str, object]] = []
        exact_indexes: list[int] = []
        for merged_index, row in merged.loc[merged["_merge"] == "both"].iterrows():
            mismatches: list[str] = []
            detail_lines: list[str] = []
            for left_column, right_column in compare_pairs:
                left_value = _resolve_value(row, left_column, "a", left_columns, right_columns)
                right_value = _resolve_value(row, right_column, "b", left_columns, right_columns)
                if normalize_text(left_value) != normalize_text(right_value):
                    mismatches.append(f"{left_column} ↔ {right_column}")
                    detail_lines.append(f"{left_column}={left_value} | {right_column}={right_value}")
            if mismatches:
                mismatch_records.append(
                    {
                        "匹配键": row.get(f"{key_a}_a", row.get(key_a, row.get(f"{key_b}_b", row.get(key_b, "")))),
                        "A表主键值": _resolve_value(row, key_a, "a", left_columns, right_columns),
                        "B表主键值": _resolve_value(row, key_b, "b", left_columns, right_columns),
                        "不一致字段": "；".join(mismatches),
                        "差异详情": "
".join(detail_lines),
                        "不一致字段数": len(mismatches),
                    }
                )
            else:
                exact_indexes.append(merged_index)

        exact_matches = merged.loc[exact_indexes].drop(columns=["__match_key"]).reset_index(drop=True)
        mismatch_details = pd.DataFrame(mismatch_records)
        if mismatch_details.empty:
            mismatch_details = pd.DataFrame(columns=["匹配键", "A表主键值", "B表主键值", "不一致字段", "差异详情", "不一致字段数"])

        stats = {
            "left_rows": len(dataframe_a),
            "right_rows": len(dataframe_b),
            "matched_rows": len(matched_records),
            "exact_match_rows": len(exact_matches),
            "missing_in_b_rows": len(missing_in_b),
            "missing_in_a_rows": len(missing_in_a),
            "mismatch_rows": len(mismatch_details),
        }

        return {
            "matched_records": matched_records,
            "exact_matches": exact_matches,
            "missing_in_b": missing_in_b,
            "missing_in_a": missing_in_a,
            "mismatch_details": mismatch_details,
            "stats": stats,
        }
