"""导出 Excel — 支持动态指标"""

from __future__ import annotations

import io

import pandas as pd


def build_export_workbook(dataframe: pd.DataFrame) -> bytes:
    """构建 Excel 工作簿，summary 页自动适配可用列"""
    buffer = io.BytesIO()

    # 动态构建摘要指标
    metrics: list[dict[str, object]] = [
        {"指标": "抓取记录数", "数值": len(dataframe)},
    ]

    if "priority" in dataframe.columns and not dataframe.empty:
        metrics.append({"指标": "高优先级数量", "数值": int((dataframe["priority"] == "高").sum())})

    if "company" in dataframe.columns and not dataframe.empty:
        metrics.append({"指标": "唯一公司/来源数", "数值": int(dataframe["company"].nunique())})
    elif "source" in dataframe.columns and not dataframe.empty:
        metrics.append({"指标": "唯一来源数", "数值": int(dataframe["source"].nunique())})

    if "category" in dataframe.columns and not dataframe.empty:
        metrics.append({"指标": "识别类别数", "数值": int(dataframe["category"].nunique())})

    if "city" in dataframe.columns and not dataframe.empty:
        non_empty_cities = dataframe["city"][dataframe["city"].astype(str).str.strip() != ""]
        if len(non_empty_cities) > 0:
            metrics.append({"指标": "涉及城市数", "数值": int(non_empty_cities.nunique())})

    summary = pd.DataFrame(metrics)

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="summary", index=False)
        dataframe.to_excel(writer, sheet_name="records", index=False)

    return buffer.getvalue()
