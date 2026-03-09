from __future__ import annotations

from difflib import SequenceMatcher

import pandas as pd

from utils.text_normalizer import normalize_company_name

try:  # pragma: no cover - 依赖可选回退
    from rapidfuzz import process
except Exception:  # pragma: no cover - 依赖可选回退
    process = None


def _similarity(left: str, right: str) -> int:
    return int(SequenceMatcher(None, left, right).ratio() * 100)


def build_fuzzy_matches(
    left_dataframe: pd.DataFrame,
    right_dataframe: pd.DataFrame,
    left_key: str,
    right_key: str,
    score_threshold: int = 85,
    limit_per_row: int = 3,
) -> pd.DataFrame:
    if left_dataframe.empty or right_dataframe.empty:
        return pd.DataFrame(columns=["A表候选", "B表候选", "相似度", "A表索引", "B表索引"])

    left_values = [
        (index, str(value), normalize_company_name(value))
        for index, value in left_dataframe[left_key].items()
        if str(value).strip()
    ]
    right_values = [
        (index, str(value), normalize_company_name(value))
        for index, value in right_dataframe[right_key].items()
        if str(value).strip()
    ]

    if not left_values or not right_values:
        return pd.DataFrame(columns=["A表候选", "B表候选", "相似度", "A表索引", "B表索引"])

    records: list[dict[str, object]] = []
    right_lookup = {normalized: (idx, raw) for idx, raw, normalized in right_values}
    normalized_right = [normalized for _, _, normalized in right_values]

    for left_index, left_raw, left_normalized in left_values:
        if not left_normalized:
            continue
        if process is not None:
            candidates = process.extract(left_normalized, normalized_right, limit=limit_per_row)
            for match_value, score, _ in candidates:
                if score < score_threshold or match_value not in right_lookup:
                    continue
                right_index, right_raw = right_lookup[match_value]
                records.append(
                    {
                        "A表候选": left_raw,
                        "B表候选": right_raw,
                        "相似度": int(score),
                        "A表索引": left_index,
                        "B表索引": right_index,
                    }
                )
        else:
            scored = []
            for right_index, right_raw, right_normalized in right_values:
                score = _similarity(left_normalized, right_normalized)
                if score >= score_threshold:
                    scored.append((score, right_index, right_raw))
            for score, right_index, right_raw in sorted(scored, reverse=True)[:limit_per_row]:
                records.append(
                    {
                        "A表候选": left_raw,
                        "B表候选": right_raw,
                        "相似度": int(score),
                        "A表索引": left_index,
                        "B表索引": right_index,
                    }
                )

    dataframe = pd.DataFrame(records)
    if dataframe.empty:
        return pd.DataFrame(columns=["A表候选", "B表候选", "相似度", "A表索引", "B表索引"])
    return dataframe.sort_values(by=["相似度", "A表候选"], ascending=[False, True]).reset_index(drop=True)
