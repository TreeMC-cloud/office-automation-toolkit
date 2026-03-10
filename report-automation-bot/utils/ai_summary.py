"""智能摘要 — 趋势判断、异常描述、集中度分析、动态建议"""

from __future__ import annotations

import pandas as pd


def generate_summary(
    overview: dict,
    trend_df: pd.DataFrame,
    dimension_df: pd.DataFrame,
    value_label: str,
    dimension_label: str,
    trend_info: dict | None = None,
    data_quality: dict | None = None,
) -> str:
    lines: list[str] = []

    # 1. 基础概览
    lines.append(f"本次共处理 {overview['total_records']:,} 条记录。")
    lines.append(
        f"{value_label} 总量 {overview['total_value']:,.2f}，"
        f"均值 {overview['average_value']:,.2f}，"
        f"中位数 {overview.get('median_value', 0):,.2f}。"
    )
    lines.append(
        f"最大值 {overview.get('max_value', 0):,.2f}，"
        f"最小值 {overview.get('min_value', 0):,.2f}，"
        f"标准差 {overview.get('std_value', 0):,.2f}。"
    )
    lines.append(
        f"最新统计周期 {overview['latest_period']}，"
        f"该周期 {value_label} 为 {overview['latest_period_value']:,.2f}。"
    )
    lines.append("")

    # 2. 趋势分析
    if trend_info:
        direction = trend_info.get("direction", "")
        if direction and direction != "数据不足":
            lines.append(f"📈 趋势判断：{direction}。")

        # 环比
        if len(trend_df) >= 2:
            try:
                cur = float(trend_df.iloc[-1][value_label])
                prev = float(trend_df.iloc[-2][value_label])
                if prev != 0:
                    rate = (cur - prev) / prev * 100
                    arrow = "↑" if rate >= 0 else "↓"
                    lines.append(f"最近一期环比变化 {arrow} {abs(rate):.1f}%。")
            except (ValueError, TypeError, KeyError):
                pass

        # 异常波动
        anomalies = trend_info.get("anomalies", [])
        if anomalies:
            lines.append(f"⚠️ 检测到 {len(anomalies)} 个异常波动周期：")
            for a in anomalies[:5]:
                lines.append(f"  · {a['period']}：{a['value']:,.2f}（{a['label']}，Z={a['z_score']}）")
        lines.append("")

    # 3. 维度分析
    if not dimension_df.empty and len(dimension_df) > 0:
        top = dimension_df.iloc[0]
        top_name = str(top.iloc[0])
        top_val = top.iloc[1]
        top_pct = str(top.get("占比", "")) if "占比" in dimension_df.columns else ""

        lines.append(f"🏆 {dimension_label} 维度中表现最高的是「{top_name}」，")
        if top_pct:
            lines.append(f"   {value_label} 为 {top_val:,.2f}，占比 {top_pct}。")
        else:
            lines.append(f"   {value_label} 为 {top_val:,.2f}。")

        # 集中度
        if "占比" in dimension_df.columns and len(dimension_df) >= 2:
            pct_str = str(dimension_df.iloc[0]["占比"]).replace("%", "")
            try:
                pct = float(pct_str)
                if pct > 50:
                    lines.append(f"   ⚡ 集中度较高：Top 1 占比超过 50%，建议关注单一依赖风险。")
            except ValueError:
                pass

        # CR3 集中度
        if "占比" in dimension_df.columns and len(dimension_df) >= 3:
            try:
                cr3 = sum(float(str(dimension_df.iloc[i]["占比"]).replace("%", "").replace("-", "0")) for i in range(min(3, len(dimension_df))))
                if cr3 > 80:
                    lines.append(f"   ⚡ Top 3 集中度 {cr3:.1f}%，市场高度集中。")
                elif cr3 > 60:
                    lines.append(f"   📊 Top 3 集中度 {cr3:.1f}%，市场中度集中。")
            except (ValueError, IndexError):
                pass

        lines.append("")

    # 4. 数据质量
    if data_quality:
        issues = []
        dup_rate = data_quality.get("duplicate_rate", "0%")
        miss_rate = data_quality.get("missing_rate", "0%")
        date_invalid = data_quality.get("date_invalid_rows", 0)

        if float(dup_rate.replace("%", "")) > 5:
            issues.append(f"重复率 {dup_rate}")
        if float(miss_rate.replace("%", "")) > 10:
            issues.append(f"缺失率 {miss_rate}")
        if date_invalid > 0:
            issues.append(f"{date_invalid} 行日期无法解析")

        if issues:
            lines.append(f"📋 数据质量提示：{'，'.join(issues)}。建议检查源数据。")
        else:
            lines.append("📋 数据质量良好，未发现明显问题。")
        lines.append("")

    # 5. 动态建议
    lines.append("💡 建议：")
    suggestions = _generate_suggestions(overview, trend_info, dimension_df, value_label)
    for s in suggestions:
        lines.append(f"  · {s}")

    return "\n".join(lines)


def _generate_suggestions(
    overview: dict, trend_info: dict | None,
    dimension_df: pd.DataFrame, value_label: str,
) -> list[str]:
    suggestions = []

    if trend_info:
        direction = trend_info.get("direction", "")
        anomalies = trend_info.get("anomalies", [])

        if "下降" in direction:
            suggestions.append(f"{value_label} 呈下降趋势，建议排查原因并制定改善措施。")
        elif "上升" in direction:
            suggestions.append(f"{value_label} 持续上升，建议分析增长驱动因素以便复制。")

        if anomalies:
            suggestions.append("存在异常波动周期，建议逐一排查是否为数据录入错误或真实业务波动。")

    std = overview.get("std_value", 0)
    avg = overview.get("average_value", 0)
    if avg > 0 and std / avg > 0.5:
        suggestions.append(f"{value_label} 波动较大（变异系数 {std/avg:.0%}），建议关注稳定性。")

    if not suggestions:
        suggestions.append("各项指标表现正常，建议持续监控。")

    return suggestions
