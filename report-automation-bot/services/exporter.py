from __future__ import annotations

import io

import pandas as pd


def build_report_workbook(
    raw_dataframe: pd.DataFrame,
    overview: dict[str, object],
    trend_dataframe: pd.DataFrame,
    dimension_dataframe: pd.DataFrame,
    summary_text: str,
) -> bytes:
    buffer = io.BytesIO()
    overview_table = pd.DataFrame([{"指标": key, "数值": value} for key, value in overview.items()])
    summary_table = pd.DataFrame({"结论摘要": summary_text.splitlines() or [summary_text]})
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        overview_table.to_excel(writer, sheet_name="overview", index=False)
        trend_dataframe.to_excel(writer, sheet_name="trend", index=False)
        dimension_dataframe.to_excel(writer, sheet_name="dimension", index=False)
        raw_dataframe.to_excel(writer, sheet_name="raw_data", index=False)
        summary_table.to_excel(writer, sheet_name="summary_text", index=False)
    return buffer.getvalue()
