"""列映射推荐 — 语义组匹配 + 字符串相似度，支持中英文列名"""

from __future__ import annotations

from utils.text_normalizer import normalize_column_name

try:
    from rapidfuzz import fuzz
    _sim = lambda a, b: fuzz.token_sort_ratio(a, b)
except ImportError:
    from difflib import SequenceMatcher
    _sim = lambda a, b: SequenceMatcher(None, a, b).ratio() * 100


# 语义组：同一组内的列名被认为是同义词
SEMANTIC_GROUPS: list[set[str]] = [
    # 标识类
    {"编号", "编码", "代码", "序号", "id", "code", "no", "number", "num", "序列号", "工号"},
    # 名称类
    {"名称", "姓名", "公司名", "企业名", "客户名", "name", "companyname", "customername", "fullname"},
    # 金额类
    {"金额", "总额", "价格", "单价", "费用", "成本", "amount", "price", "cost", "total", "sum", "fee"},
    # 数量类
    {"数量", "件数", "个数", "qty", "quantity", "count"},
    # 日期类
    {"日期", "时间", "创建时间", "更新时间", "date", "time", "datetime", "createdat", "updatedat", "timestamp"},
    # 地址类
    {"地址", "地区", "城市", "省份", "address", "city", "region", "province", "location", "area"},
    # 联系方式
    {"电话", "手机", "联系方式", "phone", "mobile", "tel", "telephone", "contact"},
    # 邮箱
    {"邮箱", "邮件", "email", "mail"},
    # 状态类
    {"状态", "阶段", "status", "state", "stage", "phase"},
    # 备注类
    {"备注", "说明", "描述", "remark", "note", "description", "comment", "memo"},
    # 类型类
    {"类型", "分类", "类别", "type", "category", "class", "kind"},
]


def recommend_key_columns(cols_a: list[str], cols_b: list[str]) -> list[tuple[str, str, int]]:
    """推荐主键列对，返回 [(col_a, col_b, score), ...] 按分数降序"""
    results = []
    for ca in cols_a:
        na = normalize_column_name(ca)
        for cb in cols_b:
            nb = normalize_column_name(cb)
            score = _column_similarity(na, nb)
            if score >= 50:
                results.append((ca, cb, score))
    results.sort(key=lambda x: x[2], reverse=True)
    return results


def recommend_field_mapping(
    cols_a: list[str], cols_b: list[str],
) -> list[tuple[str, str, int, str]]:
    """
    推荐字段映射，返回 [(col_a, col_b, score, method), ...]

    使用贪心 + 双向验证：A→B 最佳匹配必须也是 B→A 的最佳匹配。
    """
    results = []
    used_b: set[str] = set()

    # 计算所有 A→B 的分数矩阵
    score_matrix: dict[str, list[tuple[str, int, str]]] = {}
    for ca in cols_a:
        na = normalize_column_name(ca)
        candidates = []
        for cb in cols_b:
            nb = normalize_column_name(cb)
            score = _column_similarity(na, nb)
            method = "语义" if _semantic_match(na, nb) else "相似度"
            candidates.append((cb, score, method))
        candidates.sort(key=lambda x: x[1], reverse=True)
        score_matrix[ca] = candidates

    # 反向矩阵 B→A
    reverse_best: dict[str, str] = {}
    for cb in cols_b:
        nb = normalize_column_name(cb)
        best_a, best_score = "", 0
        for ca in cols_a:
            na = normalize_column_name(ca)
            score = _column_similarity(na, nb)
            if score > best_score:
                best_score = score
                best_a = ca
        if best_a:
            reverse_best[cb] = best_a

    # 贪心 + 双向验证
    for ca in cols_a:
        for cb, score, method in score_matrix[ca]:
            if cb in used_b or score < 50:
                continue
            # 双向验证：B 的最佳匹配也是 A
            if reverse_best.get(cb) == ca:
                results.append((ca, cb, score, method))
                used_b.add(cb)
                break

    results.sort(key=lambda x: x[2], reverse=True)
    return results


# ---------------------------------------------------------------------------
# 内部函数
# ---------------------------------------------------------------------------

def _column_similarity(na: str, nb: str) -> int:
    """计算两个标准化列名的相似度（0-100）"""
    if na == nb:
        return 100
    if _semantic_match(na, nb):
        return 95
    # 子串包含（较长的包含较短的）
    if len(na) >= 2 and len(nb) >= 2:
        if na in nb or nb in na:
            return 85
    return int(_sim(na, nb))


def _semantic_match(na: str, nb: str) -> bool:
    """检查两个标准化列名是否属于同一语义组"""
    for group in SEMANTIC_GROUPS:
        if na in group and nb in group:
            return True
    return False
