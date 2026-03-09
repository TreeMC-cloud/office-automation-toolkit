"""核对报告生成 — 结构化文本，含百分比、上下文、严重程度分级"""

from __future__ import annotations

from datetime import datetime


def generate_report(
    stats: dict,
    compare_pairs: list[tuple[str, str]],
    duplicates_a_count: int = 0,
    duplicates_b_count: int = 0,
    fuzzy_count: int = 0,
    file_a_name: str = "",
    file_b_name: str = "",
    tolerance: float = 0.0,
) -> str:
    """生成结构化核对报告"""
    lines: list[str] = []

    # 标题
    lines.append("=" * 60)
    lines.append("           Excel 智能核对报告")
    lines.append("=" * 60)
    lines.append("")

    # 上下文信息
    lines.append("【核对信息】")
    lines.append(f"  生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if file_a_name:
        lines.append(f"  文件 A：{file_a_name}")
    if file_b_name:
        lines.append(f"  文件 B：{file_b_name}")
    if compare_pairs:
        pairs_str = "、".join(f"{a}↔{b}" for a, b in compare_pairs)
        lines.append(f"  比对字段：{pairs_str}")
    if tolerance > 0:
        lines.append(f"  数值容差：{tolerance}")
    lines.append("")

    # 数据概览
    left = stats.get("left_rows", 0)
    right = stats.get("right_rows", 0)
    matched = stats.get("matched_rows", 0)
    exact = stats.get("exact_match_rows", 0)
    mismatch = stats.get("mismatch_rows", 0)
    miss_b = stats.get("missing_in_b_rows", 0)
    miss_a = stats.get("missing_in_a_rows", 0)

    lines.append("【数据概览】")
    lines.append(f"  A 表记录数：{left}")
    lines.append(f"  B 表记录数：{right}")
    lines.append("")

    # 匹配结果
    lines.append("【匹配结果】")
    match_rate = stats.get("match_rate", "0%")
    exact_rate = stats.get("exact_rate", "0%")
    lines.append(f"  成功匹配：{matched} 条（匹配率 {match_rate}）")
    lines.append(f"  完全一致：{exact} 条（一致率 {exact_rate}）")
    lines.append(f"  字段不一致：{mismatch} 条")
    lines.append(f"  A 有 B 无：{miss_b} 条")
    lines.append(f"  B 有 A 无：{miss_a} 条")
    lines.append("")

    # 重复与模糊
    lines.append("【数据质量】")
    lines.append(f"  A 表重复记录：{duplicates_a_count} 条")
    lines.append(f"  B 表重复记录：{duplicates_b_count} 条")
    lines.append(f"  模糊匹配候选：{fuzzy_count} 对")
    lines.append("")

    # 诊断与建议
    lines.append("【诊断与建议】")
    issues = _diagnose(stats, duplicates_a_count, duplicates_b_count, fuzzy_count)
    if not issues:
        lines.append("  ✅ 数据质量良好，未发现明显问题。")
    else:
        for level, msg in issues:
            icon = {"严重": "🔴", "警告": "🟡", "提示": "🔵"}.get(level, "⚪")
            lines.append(f"  {icon} [{level}] {msg}")

    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)


def _diagnose(stats: dict, dup_a: int, dup_b: int, fuzzy: int) -> list[tuple[str, str]]:
    """根据数据生成诊断建议，按严重程度排序"""
    issues: list[tuple[str, str]] = []

    left = stats.get("left_rows", 0)
    right = stats.get("right_rows", 0)
    matched = stats.get("matched_rows", 0)
    miss_b = stats.get("missing_in_b_rows", 0)
    miss_a = stats.get("missing_in_a_rows", 0)
    mismatch = stats.get("mismatch_rows", 0)

    # 匹配率过低
    if left > 0:
        rate = matched / left
        if rate < 0.5:
            issues.append(("严重", f"匹配率仅 {rate:.0%}，请检查主键列是否选择正确"))
        elif rate < 0.8:
            issues.append(("警告", f"匹配率 {rate:.0%}，部分记录未能匹配"))

    # 大量缺失
    if miss_b > 0 and left > 0 and miss_b / left > 0.2:
        issues.append(("警告", f"A 表有 {miss_b} 条记录在 B 表中找不到（{miss_b/left:.0%}）"))
    if miss_a > 0 and right > 0 and miss_a / right > 0.2:
        issues.append(("警告", f"B 表有 {miss_a} 条记录在 A 表中找不到（{miss_a/right:.0%}）"))

    # 字段不一致
    if mismatch > 0 and matched > 0 and mismatch / matched > 0.3:
        issues.append(("警告", f"已匹配记录中 {mismatch/matched:.0%} 存在字段差异"))

    # 重复记录
    if dup_a > 0:
        issues.append(("提示", f"A 表存在 {dup_a} 条重复记录，可能影响匹配准确性"))
    if dup_b > 0:
        issues.append(("提示", f"B 表存在 {dup_b} 条重复记录，可能影响匹配准确性"))

    # 模糊匹配
    if fuzzy > 0:
        issues.append(("提示", f"发现 {fuzzy} 对模糊匹配候选，建议人工核实"))

    # 数据量差异大
    if left > 0 and right > 0:
        ratio = max(left, right) / min(left, right)
        if ratio > 2:
            issues.append(("提示", f"两表数据量差异较大（{left} vs {right}），请确认数据范围一致"))

    return issues
