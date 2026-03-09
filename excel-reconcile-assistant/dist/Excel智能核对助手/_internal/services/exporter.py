from __future__ import annotations

import io

import pandas as pd


def _write_dataframe(writer: pd.ExcelWriter, dataframe: pd.DataFrame, sheet_name: str) -> None:
    if dataframe is None or dataframe.empty:
        pd.DataFrame(columns=dataframe.columns if dataframe is not None else []).to_excel(writer, sheet_name=sheet_name, index=False)
        return
    dataframe.to_excel(writer, sheet_name=sheet_name, index=False)


def build_export_workbook(
    results: dict,
    duplicates_a: pd.DataFrame,
    duplicates_b: pd.DataFrame,
    fuzzy_matches: pd.DataFrame,
    report_text: str,
) -> bytes:
    buffer = io.BytesIO()
    summary = pd.DataFrame(
        [{"指标": key, "数值": value} for key, value in results["stats"].items()]
    )
    report_table = pd.DataFrame({"核对报告": report_text.splitlines() or [report_text]})
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="summary", index=False)
        _write_dataframe(writer, results["matched_records"], "matched_records")
        _write_dataframe(writer, results["exact_matches"], "exact_matches")
        _write_dataframe(writer, results["missing_in_b"], "missing_in_b")
        _write_dataframe(writer, results["missing_in_a"], "missing_in_a")
        _write_dataframe(writer, results["mismatch_details"], "mismatch_details")
        _write_dataframe(writer, duplicates_a, "duplicates_a")
        _write_dataframe(writer, duplicates_b, "duplicates_b")
        _write_dataframe(writer, fuzzy_matches, "fuzzy_candidates")
        report_table.to_excel(writer, sheet_name="report", index=False)
    return buffer.getvalue()
