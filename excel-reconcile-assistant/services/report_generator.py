from __future__ import annotations


def generate_report(
    stats: dict[str, int],
    compare_pairs: list[tuple[str, str]],
    duplicates_a_count: int,
    duplicates_b_count: int,
    fuzzy_count: int,
) -> str:
    compare_text = "、".join(f"{left} ↔ {right}" for left, right in compare_pairs)
    lines = [
        "Excel 核对报告",
        "==========",
        f"A 表记录数：{stats['left_rows']}",
        f"B 表记录数：{stats['right_rows']}",
        f"匹配成功记录：{stats['matched_rows']}",
        f"完全一致记录：{stats['exact_match_rows']}",
        f"A 表存在但 B 表缺失：{stats['missing_in_b_rows']}",
        f"B 表存在但 A 表缺失：{stats['missing_in_a_rows']}",
        f"字段不一致记录：{stats['mismatch_rows']}",
        f"A 表重复记录：{duplicates_a_count}",
        f"B 表重复记录：{duplicates_b_count}",
        f"模糊匹配候选：{fuzzy_count}",
    ]
    if compare_pairs:
        lines.append(f"重点比对字段：{compare_text}")

    if stats["missing_in_b_rows"] or stats["missing_in_a_rows"]:
        lines.append("建议优先处理缺失记录，再处理字段差异，这样可以减少重复沟通成本。")
    if stats["mismatch_rows"]:
        lines.append("存在字段不一致记录，建议重点关注联系人、手机号、金额等关键字段。")
    if fuzzy_count:
        lines.append("模糊匹配中发现疑似同名记录，可用于二次人工确认。")
    if not any(
        [
            stats["missing_in_b_rows"],
            stats["missing_in_a_rows"],
            stats["mismatch_rows"],
            duplicates_a_count,
            duplicates_b_count,
        ]
    ):
        lines.append("未发现明显异常，本次核对结果整体较为稳定。")
    return "\n".join(lines)
