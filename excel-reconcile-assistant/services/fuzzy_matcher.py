"""模糊匹配 — 修复同名覆盖 bug，批量匹配优化"""

from __future__ import annotations

from collections import defaultdict

import pandas as pd

from utils.text_normalizer import normalize_text

try:
    from rapidfuzz import fuzz, process as rf_process
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False
    from difflib import SequenceMatcher


def build_fuzzy_matches(
    missing_left: pd.DataFrame,
    missing_right: pd.DataFrame,
    key_left: str,
    key_right: str,
    score_threshold: int = 80,
    max_candidates: int = 3,
) -> pd.DataFrame:
    """
    对缺失记录做模糊匹配，返回候选匹配对。

    修复：right_lookup 改为 list 存储，避免同名覆盖。
    优化：使用 rapidfuzz.process.extract 批量匹配。
    """
    if missing_left.empty or missing_right.empty:
        return pd.DataFrame(columns=["A值", "B值", "相似度", "置信等级"])

    # 构建右侧查找表：normalized → [(index, raw_value), ...]
    right_lookup: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for idx, row in missing_right.iterrows():
        raw = str(row.get(key_right, ""))
        normalized = normalize_text(raw)
        if normalized:
            right_lookup[normalized].append((idx, raw))

    if not right_lookup:
        return pd.DataFrame(columns=["A值", "B值", "相似度", "置信等级"])

    # 左侧待匹配值
    left_items = []
    for idx, row in missing_left.iterrows():
        raw = str(row.get(key_left, ""))
        normalized = normalize_text(raw)
        if normalized:
            left_items.append((idx, raw, normalized))

    if not left_items:
        return pd.DataFrame(columns=["A值", "B值", "相似度", "置信等级"])

    right_keys = list(right_lookup.keys())
    results = []

    if HAS_RAPIDFUZZ:
        results = _match_rapidfuzz(left_items, right_keys, right_lookup, score_threshold, max_candidates)
    else:
        results = _match_difflib(left_items, right_keys, right_lookup, score_threshold, max_candidates)

    if not results:
        return pd.DataFrame(columns=["A值", "B值", "相似度", "置信等级"])

    df = pd.DataFrame(results)
    df = df.sort_values("相似度", ascending=False).reset_index(drop=True)
    return df


def _match_rapidfuzz(
    left_items: list[tuple],
    right_keys: list[str],
    right_lookup: dict,
    threshold: int,
    max_candidates: int,
) -> list[dict]:
    """使用 rapidfuzz 批量匹配"""
    results = []
    for _, raw_left, norm_left in left_items:
        matches = rf_process.extract(
            norm_left, right_keys,
            scorer=fuzz.token_sort_ratio,
            limit=max_candidates,
            score_cutoff=threshold,
        )
        for match_key, score, _ in matches:
            for _, raw_right in right_lookup[match_key]:
                results.append({
                    "A值": raw_left,
                    "B值": raw_right,
                    "相似度": round(score, 1),
                    "置信等级": _confidence_level(score),
                })
    return results


def _match_difflib(
    left_items: list[tuple],
    right_keys: list[str],
    right_lookup: dict,
    threshold: int,
    max_candidates: int,
) -> list[dict]:
    """回退到 difflib（无 rapidfuzz 时）"""
    results = []
    for _, raw_left, norm_left in left_items:
        scored = []
        for rk in right_keys:
            score = SequenceMatcher(None, norm_left, rk).ratio() * 100
            if score >= threshold:
                scored.append((rk, score))
        scored.sort(key=lambda x: x[1], reverse=True)

        for rk, score in scored[:max_candidates]:
            for _, raw_right in right_lookup[rk]:
                results.append({
                    "A值": raw_left,
                    "B值": raw_right,
                    "相似度": round(score, 1),
                    "置信等级": _confidence_level(score),
                })
    return results


def _confidence_level(score: float) -> str:
    if score >= 95:
        return "极高"
    if score >= 90:
        return "高"
    if score >= 80:
        return "中"
    return "低"
