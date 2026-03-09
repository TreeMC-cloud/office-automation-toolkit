"""AI 标签分类 — 支持多场景（招聘/商品/新闻/论文/通用）"""

from __future__ import annotations

import re


# ---------------------------------------------------------------------------
# 分类规则（扩展版，支持多场景）
# ---------------------------------------------------------------------------
CATEGORY_RULES: dict[str, list[str]] = {
    # 招聘
    "后端开发": ["后端", "python", "java", "api", "服务端", "golang", "c++", "rust"],
    "前端开发": ["前端", "react", "vue", "小程序", "angular", "typescript", "css"],
    "数据分析": ["数据分析", "sql", "bi", "报表", "数据挖掘", "机器学习", "ai"],
    "运营支持": ["运营", "客服", "支持", "协调", "行政"],
    "产品设计": ["产品经理", "ui", "ux", "设计", "交互"],
    # 商品
    "电子产品": ["手机", "电脑", "笔记本", "平板", "gpu", "cpu", "显卡", "内存", "ssd"],
    "家居生活": ["家具", "家电", "厨房", "卫浴", "家居"],
    "服饰美妆": ["服装", "鞋", "包", "化妆品", "护肤", "美妆"],
    # 新闻
    "科技资讯": ["科技", "互联网", "ai", "人工智能", "芯片", "5g", "区块链"],
    "财经新闻": ["股票", "基金", "理财", "金融", "经济", "gdp", "央行"],
    "社会民生": ["教育", "医疗", "房价", "就业", "社保", "养老"],
    # 论文
    "学术研究": ["论文", "研究", "实验", "算法", "模型", "数据集"],
}

PRIORITY_RULES: dict[str, list[str]] = {
    "高": ["急招", "核心", "重点", "负责人", "高级", "热门", "爆款", "突发", "重磅", "独家"],
    "中": ["熟悉", "参与", "协助", "推荐", "精选", "关注"],
}

CITIES = [
    "北京", "上海", "广州", "深圳", "杭州", "苏州", "成都",
    "武汉", "南京", "西安", "重庆", "天津", "长沙", "郑州",
    "青岛", "大连", "厦门", "合肥", "珠海", "东莞",
]

STOPWORDS = {
    "负责", "以及", "相关", "熟悉", "能够", "工作", "岗位", "经验",
    "以上", "进行", "我们", "团队", "公司", "提供", "要求", "具有",
    "了解", "使用", "通过", "支持", "包括", "其他", "优秀",
}


def _detect_category(text: str) -> str:
    """根据文本内容匹配最佳分类"""
    lowered = text.lower()
    scores: dict[str, int] = {}
    for label, keywords in CATEGORY_RULES.items():
        score = sum(1 for kw in keywords if kw in lowered)
        if score > 0:
            scores[label] = score
    if not scores:
        return "综合信息"
    return max(scores, key=scores.get)  # type: ignore[arg-type]


def _detect_priority(text: str) -> str:
    lowered = text.lower()
    for label, keywords in PRIORITY_RULES.items():
        if any(keyword in lowered for keyword in keywords):
            return label
    return "低"


def _detect_city(text: str) -> str:
    for city in CITIES:
        if city in text:
            return city
    return ""


def _extract_keywords(text: str, top_n: int = 5) -> str:
    words = re.findall(r"[A-Za-z]+|[\u4e00-\u9fff]{2,}", text)
    filtered = []
    for word in words:
        normalized = word.lower()
        if normalized in STOPWORDS or len(normalized) < 2:
            continue
        filtered.append(word)
    unique = []
    for word in filtered:
        if word not in unique:
            unique.append(word)
    return "、".join(unique[:top_n])


def _build_summary(record: dict[str, str], category: str, priority: str, city: str) -> str:
    base = record.get("snippet") or record.get("summary") or record.get("content") or record.get("title", "")
    base = base[:80] + ("..." if len(base) > 80 else "")
    parts = [category, f"优先级{priority}"]
    if city:
        parts.append(city)
    return " | ".join(parts) + f" | {base}"


def tag_records(records: list[dict[str, str]]) -> list[dict[str, str]]:
    """对记录列表进行标签分类"""
    tagged: list[dict[str, str]] = []
    for record in records:
        merged_text = " ".join(
            str(record.get(field, ""))
            for field in ["title", "snippet", "summary", "content", "company", "location", "abstract"]
        )
        category = _detect_category(merged_text)
        priority = _detect_priority(merged_text)
        city = record.get("location") or _detect_city(merged_text)
        keywords = _extract_keywords(merged_text)
        tagged.append(
            {
                **record,
                "category": category,
                "priority": priority,
                "city": city,
                "keywords": keywords,
                "ai_summary": _build_summary(record, category, priority, city),
            }
        )
    return tagged
