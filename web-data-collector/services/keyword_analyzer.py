"""关键词意图分析 — 根据用户输入的关键词推断数据类别并构建搜索策略"""

from __future__ import annotations

import re
from urllib.parse import quote_plus

# ---------------------------------------------------------------------------
# 类别定义：关键词 → 类别映射
# ---------------------------------------------------------------------------
CATEGORY_RULES: dict[str, list[str]] = {
    "招聘": [
        "招聘", "求职", "岗位", "职位", "简历", "面试", "薪资", "薪酬",
        "工资", "offer", "hr", "人才", "校招", "社招", "实习",
        "hiring", "job", "career", "recruit",
    ],
    "商品": [
        "价格", "报价", "多少钱", "购买", "优惠", "折扣", "促销",
        "淘宝", "京东", "拼多多", "电商", "商品", "产品",
        "price", "buy", "shop", "deal",
    ],
    "新闻": [
        "新闻", "资讯", "报道", "头条", "快讯", "事件", "热点",
        "最新", "今日", "动态", "公告", "发布",
        "news", "breaking", "headline",
    ],
    "论文": [
        "论文", "学术", "研究", "期刊", "文献", "摘要", "引用",
        "paper", "research", "journal", "arxiv", "scholar",
    ],
}

# 每个类别期望提取的字段
CATEGORY_FIELDS: dict[str, list[str]] = {
    "招聘": ["title", "company", "location", "salary", "publish_date", "content"],
    "商品": ["title", "price", "source", "publish_date", "content"],
    "新闻": ["title", "source", "publish_date", "author", "content"],
    "论文": ["title", "authors", "source", "publish_date", "abstract"],
    "通用": ["title", "source", "publish_date", "content"],
}


def _detect_category(keyword: str) -> str:
    """根据关键词匹配类别，返回最高匹配度的类别"""
    lowered = keyword.lower()
    scores: dict[str, int] = {}
    for category, triggers in CATEGORY_RULES.items():
        score = sum(1 for t in triggers if t in lowered)
        if score > 0:
            scores[category] = score
    if not scores:
        return "通用"
    return max(scores, key=scores.get)  # type: ignore[arg-type]


def _build_search_queries(keyword: str, category: str) -> list[str]:
    """根据关键词和类别生成多个搜索查询变体"""
    queries = [keyword]

    # 根据类别追加限定词
    suffixes: dict[str, list[str]] = {
        "招聘": ["招聘信息", "最新岗位"],
        "商品": ["价格", "报价"],
        "新闻": ["最新消息", "新闻"],
        "论文": ["学术论文", "研究"],
        "通用": [],
    }
    for suffix in suffixes.get(category, []):
        variant = f"{keyword} {suffix}"
        if variant != keyword:
            queries.append(variant)

    return queries[:3]  # 最多 3 个查询


def _build_search_urls(queries: list[str], max_results_per_query: int = 10) -> list[str]:
    """将查询列表转换为 Bing 搜索 URL"""
    urls = []
    for query in queries:
        encoded = quote_plus(query)
        url = f"https://www.bing.com/search?q={encoded}&count={max_results_per_query}"
        urls.append(url)
    return urls


def analyze_keyword(keyword: str, category_override: str = "") -> dict:
    """
    分析关键词，返回搜索策略。

    Parameters
    ----------
    keyword : str
        用户输入的关键词，如 "Python 招聘 北京"
    category_override : str
        用户手动指定的类别（空字符串表示自动检测）

    Returns
    -------
    dict
        - category: 推断的数据类别
        - search_queries: 生成的搜索查询列表
        - expected_fields: 该类别下期望提取的字段列表
        - search_urls: 构建好的 Bing 搜索 URL
    """
    keyword = keyword.strip()
    if not keyword:
        raise ValueError("关键词不能为空")

    category = category_override if category_override and category_override != "自动" else _detect_category(keyword)
    queries = _build_search_queries(keyword, category)
    urls = _build_search_urls(queries)
    fields = CATEGORY_FIELDS.get(category, CATEGORY_FIELDS["通用"])

    return {
        "category": category,
        "search_queries": queries,
        "expected_fields": fields,
        "search_urls": urls,
    }
