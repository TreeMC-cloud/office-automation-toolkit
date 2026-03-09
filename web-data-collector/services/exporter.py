"""导出 Excel — 动态指标、质量评分统计"""

from __future__ import annotations

import io

import pandas as pd


def build_export_workbook(dataframe: pd.DataFrame) -> bytes:
    """构建 Excel 工作簿，summary 页自动适配可用列"""
    buffer = io.BytesIO()

    metrics: list[dict[str, object]] = [
        {"指标": "采集记录数", "数值": len(dataframe)},
    ]

    if "quality_score" in dataframe.columns and not dataframe.empty:
        scores = pd.to_numeric(dataframe["quality_score"], errors="coerce")
        avg_score = scores.mean()
        if pd.notna(avg_score):
            metrics.append({"指标": "平均质量评分", "数值": round(avg_score, 1)})

    if "priority" in dataframe.columns and not dataframe.empty:
        metrics.append({"指标": "高优先级数量", "数值": int((dataframe["priority"] == "高").sum())})

    if "brand" in dataframe.columns and not dataframe.empty:
        brands = dataframe["brand"][dataframe["brand"].astype(str).str.strip() != ""]
        if len(brands) > 0:
            metrics.append({"指标": "涉及品牌数", "数值": int(brands.nunique())})

    if "company" in dataframe.columns and not dataframe.empty:
        companies = dataframe["company"][dataframe["company"].astype(str).str.strip() != ""]
        if len(companies) > 0:
            metrics.append({"指标": "唯一公司/来源数", "数值": int(companies.nunique())})
    elif "source" in dataframe.columns and not dataframe.empty:
        sources = dataframe["source"][dataframe["source"].astype(str).str.strip() != ""]
        if len(sources) > 0:
            metrics.append({"指标": "唯一来源数", "数值": int(sources.nunique())})

    if "search_engine" in dataframe.columns and not dataframe.empty:
        engines = dataframe["search_engine"][dataframe["search_engine"].astype(str).str.strip() != ""]
        if len(engines) > 0:
            metrics.append({"指标": "搜索引擎覆盖", "数值": ", ".join(engines.unique())})

    if "category" in dataframe.columns and not dataframe.empty:
        metrics.append({"指标": "识别类别数", "数值": int(dataframe["category"].nunique())})

    if "sentiment" in dataframe.columns and not dataframe.empty:
        sentiments = dataframe["sentiment"].value_counts()
        for s_name, s_count in sentiments.items():
            metrics.append({"指标": f"情感-{s_name}", "数值": int(s_count)})

    summary = pd.DataFrame(metrics)

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="summary", index=False)
        dataframe.to_excel(writer, sheet_name="records", index=False)

    return buffer.getvalue()
