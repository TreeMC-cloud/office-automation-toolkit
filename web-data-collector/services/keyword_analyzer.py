"""关键词意图分析引擎 — 产品名识别、意图分类、多角度查询生成"""

from __future__ import annotations

import re
from urllib.parse import quote_plus

# ---------------------------------------------------------------------------
# 意图类型定义
# ---------------------------------------------------------------------------
# 意图 = 用户想要什么类型的信息
INTENT_TYPES = {
    "商品比价": {
        "triggers": [
            "价格", "报价", "多少钱", "售价", "定价", "优惠", "折扣", "促销",
            "便宜", "划算", "性价比", "购买", "入手", "下单",
            "price", "buy", "deal", "cheap", "cost",
        ],
        "fields": ["title", "price", "image_url", "source", "publish_date", "specs", "content"],
        "query_templates": [
            "{keyword} 价格",
            "{keyword} 多少钱",
            "{keyword} 各平台报价",
            "{keyword} 优惠 折扣",
        ],
    },
    "产品评测": {
        "triggers": [
            "评测", "测评", "体验", "上手", "对比", "怎么样", "好不好", "值不值",
            "优缺点", "性能", "跑分", "续航", "拍照", "屏幕", "参数", "配置", "规格",
            "review", "benchmark", "test", "comparison", "spec",
        ],
        "fields": ["title", "image_url", "source", "author", "publish_date", "specs", "content"],
        "query_templates": [
            "{keyword} 评测",
            "{keyword} 深度体验",
            "{keyword} 参数配置",
            "{keyword} 优缺点",
        ],
    },
    "新闻资讯": {
        "triggers": [
            "新闻", "资讯", "报道", "头条", "快讯", "事件", "热点",
            "最新", "今日", "动态", "公告", "发布", "曝光", "爆料", "消息",
            "news", "breaking", "headline", "update", "announce",
        ],
        "fields": ["title", "source", "author", "publish_date", "content"],
        "query_templates": [
            "{keyword} 最新消息",
            "{keyword} 新闻",
            "{keyword} 最新动态",
        ],
    },
    "招聘求职": {
        "triggers": [
            "招聘", "求职", "岗位", "职位", "简历", "面试", "薪资", "薪酬",
            "工资", "offer", "hr", "人才", "校招", "社招", "实习",
            "hiring", "job", "career", "recruit",
        ],
        "fields": ["title", "company", "location", "salary", "publish_date", "content"],
        "query_templates": [
            "{keyword} 招聘",
            "{keyword} 最新岗位",
            "{keyword} 薪资待遇",
        ],
    },
    "学术论文": {
        "triggers": [
            "论文", "学术", "研究", "期刊", "文献", "摘要", "引用",
            "paper", "research", "journal", "arxiv", "scholar",
        ],
        "fields": ["title", "authors", "source", "publish_date", "abstract"],
        "query_templates": [
            "{keyword} 论文",
            "{keyword} 学术研究",
            "{keyword} paper",
        ],
    },
}

# 默认意图
DEFAULT_INTENT = {
    "fields": ["title", "source", "publish_date", "content"],
    "query_templates": [
        "{keyword}",
        "{keyword} 最新信息",
        "{keyword} 详细介绍",
    ],
}

# ---------------------------------------------------------------------------
# 知名产品/品牌模式识别
# ---------------------------------------------------------------------------
_PRODUCT_PATTERNS = [
    # 手机/电子产品型号：iPhone 17, Galaxy S25, Pixel 9, 小米15, 华为Mate70
    re.compile(r"(?i)(iphone|ipad|macbook|airpods|apple\s*watch)\s*\w*", re.IGNORECASE),
    re.compile(r"(?i)(galaxy|samsung)\s*\w+", re.IGNORECASE),
    re.compile(r"(?i)(pixel|nexus)\s*\w*", re.IGNORECASE),
    re.compile(r"(?i)(mate|nova|p\d+|pura)\s*\w*", re.IGNORECASE),
    re.compile(r"(?i)(小米|红米|redmi|poco)\s*\w*", re.IGNORECASE),
    re.compile(r"(?i)(oppo|vivo|realme|oneplus|一加)\s*\w*", re.IGNORECASE),
    # GPU/CPU
    re.compile(r"(?i)(rtx|gtx|rx|radeon|geforce)\s*\d+\w*", re.IGNORECASE),
    re.compile(r"(?i)(i[3579]|ryzen\s*\d|骁龙|天玑|dimensity|snapdragon)\s*\w*", re.IGNORECASE),
    # 汽车
    re.compile(r"(?i)(model\s*[3ysxy]|特斯拉|比亚迪|蔚来|小鹏|理想|问界|极氪)\s*\w*", re.IGNORECASE),
    # 游戏主机
    re.compile(r"(?i)(ps[456]|xbox|switch|steam\s*deck)\s*\w*", re.IGNORECASE),
    # 通用型号模式：品牌 + 数字/字母
    re.compile(r"[A-Za-z]+\s*\d+\s*(?:pro|max|ultra|plus|lite|mini|se|air)?", re.IGNORECASE),
]

_BRAND_KEYWORDS = {
    "apple", "苹果", "iphone", "ipad", "macbook",
    "samsung", "三星", "galaxy",
    "huawei", "华为", "mate", "nova",
    "xiaomi", "小米", "红米", "redmi",
    "oppo", "vivo", "realme", "oneplus", "一加",
    "google", "pixel",
    "nvidia", "amd", "intel", "英伟达", "英特尔",
    "tesla", "特斯拉", "比亚迪", "蔚来", "小鹏", "理想",
    "sony", "索尼", "任天堂", "nintendo", "微软", "microsoft",
}


def _is_product_query(keyword: str) -> bool:
    """判断关键词是否涉及具体产品"""
    lowered = keyword.lower()
    # 品牌关键词命中
    if any(brand in lowered for brand in _BRAND_KEYWORDS):
        return True
    # 型号模式命中
    for pattern in _PRODUCT_PATTERNS:
        if pattern.search(keyword):
            return True
    return False


def _detect_intent(keyword: str) -> str:
    """根据关键词检测用户意图"""
    lowered = keyword.lower()

    # 计算每个意图的匹配分数
    scores: dict[str, int] = {}
    for intent_name, intent_def in INTENT_TYPES.items():
        score = sum(1 for t in intent_def["triggers"] if t in lowered)
        if score > 0:
            scores[intent_name] = score

    if scores:
        return max(scores, key=scores.get)  # type: ignore[arg-type]

    # 没有明确意图触发词时，根据是否是产品查询来推断
    if _is_product_query(keyword):
        # 产品查询默认走"产品评测"（综合信息）
        return "产品评测"

    return ""  # 空字符串表示通用


def _build_search_queries(keyword: str, intent: str) -> list[str]:
    """根据关键词和意图生成多角度搜索查询"""
    if intent and intent in INTENT_TYPES:
        templates = INTENT_TYPES[intent]["query_templates"]
    else:
        templates = DEFAULT_INTENT["query_templates"]

    queries: list[str] = []
    seen: set[str] = set()

    # 原始关键词始终作为第一个查询
    queries.append(keyword)
    seen.add(keyword)

    for template in templates:
        query = template.format(keyword=keyword)
        if query not in seen:
            seen.add(query)
            queries.append(query)

    return queries[:5]  # 最多 5 个查询


# ---------------------------------------------------------------------------
# 搜索引擎 URL 构建
# ---------------------------------------------------------------------------
def _build_engine_urls(query: str, engines: list[str]) -> list[dict[str, str]]:
    """为单个查询构建多引擎搜索 URL"""
    encoded = quote_plus(query)
    urls = []

    engine_templates = {
        "bing": f"https://www.bing.com/search?q={encoded}&count=10",
        "baidu": f"https://www.baidu.com/s?wd={encoded}&rn=10",
        "sogou": f"https://www.sogou.com/web?query={encoded}&num=10",
    }

    for engine in engines:
        if engine in engine_templates:
            urls.append({"engine": engine, "url": engine_templates[engine], "query": query})

    return urls


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------
# 意图到中文显示名
INTENT_DISPLAY_NAMES = {
    "商品比价": "商品比价",
    "产品评测": "产品评测",
    "新闻资讯": "新闻资讯",
    "招聘求职": "招聘求职",
    "学术论文": "学术论文",
    "": "综合搜索",
}

# UI 可选的意图列表
INTENT_OPTIONS = ["自动", "商品比价", "产品评测", "新闻资讯", "招聘求职", "学术论文", "综合搜索"]


def analyze_keyword(
    keyword: str,
    intent_override: str = "",
    engines: list[str] | None = None,
) -> dict:
    """
    分析关键词，返回完整搜索策略。

    Parameters
    ----------
    keyword : str
        用户输入的关键词
    intent_override : str
        用户手动指定的意图（空或"自动"表示自动检测）
    engines : list[str]
        搜索引擎列表，默认 ["bing", "baidu"]

    Returns
    -------
    dict
        - intent: 识别的意图
        - intent_display: 意图中文显示名
        - is_product: 是否为产品查询
        - search_queries: 生成的搜索查询列表
        - expected_fields: 期望提取的字段列表
        - engine_urls: 多引擎搜索 URL 列表
    """
    keyword = keyword.strip()
    if not keyword:
        raise ValueError("关键词不能为空")

    if engines is None:
        engines = ["bing", "baidu"]

    # 意图检测
    if intent_override and intent_override not in ("自动", "综合搜索", ""):
        intent = intent_override
    else:
        intent = _detect_intent(keyword)

    is_product = _is_product_query(keyword)

    # 获取字段和查询
    if intent and intent in INTENT_TYPES:
        fields = INTENT_TYPES[intent]["fields"]
    else:
        fields = DEFAULT_INTENT["fields"]

    queries = _build_search_queries(keyword, intent)

    # 构建多引擎 URL
    all_engine_urls: list[dict[str, str]] = []
    for query in queries:
        all_engine_urls.extend(_build_engine_urls(query, engines))

    return {
        "intent": intent,
        "intent_display": INTENT_DISPLAY_NAMES.get(intent, "综合搜索"),
        "is_product": is_product,
        "search_queries": queries,
        "expected_fields": fields,
        "engine_urls": all_engine_urls,
    }
