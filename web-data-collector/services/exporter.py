from __future__ import annotations

import io

import pandas as pd


def build_export_workbook(dataframe: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    summary = pd.DataFrame(
        [
            {"指标": "抓取记录数", "数值": len(dataframe)},
            {"指标": "高优先级数量", "数值": int((dataframe['priority'] == '高').sum()) if 'priority' in dataframe.columns else 0},
            {"指标": "唯一公司数", "数值": int(dataframe['company'].nunique()) if 'company' in dataframe.columns else 0},
        ]
    )
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="summary", index=False)
        dataframe.to_excel(writer, sheet_name="records", index=False)
    return buffer.getvalue()
