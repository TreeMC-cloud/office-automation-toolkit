from __future__ import annotations

import pandas as pd


def generate_summary(
    overview: dict[str, object],
    trend_df: pd.DataFrame,
    dimension_df: pd.DataFrame,
    value_label: str,
    dimension_label: str,
) -> str:
    lines = [
        f"本次共处理 {overview['total_records']} 条记录，{value_label} 总量为 {overview['total_value']}，平均值为 {overview['average_value']}。",
        f"最新统计周期为 {overview['latest_period']}，该周期 {value_label} 为 {overview['latest_period_value']}。",
    ]
    if len(trend_df) >= 2:
        current = float(trend_df.iloc[-1][value_label])
        previous = float(trend_df.iloc[-2][value_label])
        if previous == 0:
            lines.append("最近两个周期中前一周期为 0，暂不计算变化率。")
        else:
            change_rate = round((current - previous) / previous * 100, 2)
            direction = "上升" if change_rate >= 0 else "下降"
            lines.append(f"最近两个周期相比，{value_label} {direction} {abs(change_rate)}%。")
    if not dimension_df.empty:
        top_record = dimension_df.iloc[0]
        lines.append(
            f"{dimension_label} 维度中表现最高的是 {top_record.iloc[0]}，对应 {value_label} 为 {top_record.iloc[1]}。"
        )
    lines.append("建议结合异常峰值日期与 Top 维度做进一步原因分析，再决定是否自动发送给业务方。")
    return "\n".join(lines)
