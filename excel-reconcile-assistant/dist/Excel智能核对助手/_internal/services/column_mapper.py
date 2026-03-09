from __future__ import annotations

from difflib import SequenceMatcher

from utils.text_normalizer import normalize_column_name


SEMANTIC_GROUPS = {
    "customer_id": ["客户编号", "客户id", "客户代码", "企业编号", "编号", "编码"],
    "company": ["客户名称", "公司名", "企业名称", "单位名称", "商户名称", "客户", "名称"],
    "contact": ["联系人", "联系人姓名", "负责人", "对接人", "姓名"],
    "phone": ["手机号", "电话", "联系电话", "联系方式", "手机"],
    "amount": ["金额", "订单金额", "回款金额", "总额", "销售额", "应收金额"],
    "city": ["城市", "地区", "所在城市", "省市", "区域"],
    "date": ["日期", "时间", "创建时间", "下单时间", "发布时间"],
}


def _semantic_label(column_name: str) -> str | None:
    normalized = normalize_column_name(column_name)
    for label, aliases in SEMANTIC_GROUPS.items():
        for alias in aliases:
            if normalize_column_name(alias) in normalized or normalized in normalize_column_name(alias):
                return label
    return None


def _score_pair(left: str, right: str) -> tuple[int, str]:
    left_norm = normalize_column_name(left)
    right_norm = normalize_column_name(right)
    if left_norm == right_norm:
        return 100, "列名完全一致"
    left_label = _semantic_label(left)
    right_label = _semantic_label(right)
    if left_label and right_label and left_label == right_label:
        return 94, f"语义组一致：{left_label}"
    similarity = int(SequenceMatcher(None, left_norm, right_norm).ratio() * 100)
    return similarity, "字符串相似度"


def recommend_key_columns(columns_a: list[str], columns_b: list[str], limit: int = 3) -> list[tuple[str, str, int, str]]:
    candidates: list[tuple[str, str, int, str]] = []
    for left in columns_a:
        for right in columns_b:
            score, reason = _score_pair(left, right)
            if score >= 65:
                candidates.append((left, right, score, reason))
    candidates.sort(key=lambda item: item[2], reverse=True)
    return candidates[:limit]


def recommend_field_mapping(columns_a: list[str], columns_b: list[str], limit: int = 6) -> list[tuple[str, str, int, str]]:
    used_right: set[str] = set()
    mappings: list[tuple[str, str, int, str]] = []
    for left in columns_a:
        best_right = None
        best_score = -1
        best_reason = ""
        for right in columns_b:
            if right in used_right:
                continue
            score, reason = _score_pair(left, right)
            if score > best_score:
                best_right = right
                best_score = score
                best_reason = reason
        if best_right and best_score >= 55:
            mappings.append((left, best_right, best_score, best_reason))
            used_right.add(best_right)
    mappings.sort(key=lambda item: item[2], reverse=True)
    return mappings[:limit]
