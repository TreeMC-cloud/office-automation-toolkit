"""AI 标签分类 — 产品型号识别、品牌识别、情感倾向分析、多场景分类"""

from __future__ import annotations

import re


# ---------------------------------------------------------------------------
# 分类规则
# ---------------------------------------------------------------------------
CATEGORY_RULES: dict[str, list[str]] = {
    # 招聘
    "后端开发": ["后端", "python", "java", "api", "服务端", "golang", "c++", "rust", "node"],
    "前端开发": ["前端", "react", "vue", "小程序", "angular", "typescript", "css", "flutter"],
    "数据分析": ["数据分析", "sql", "bi", "报表", "数据挖掘", "机器学习", "ai", "深度学习"],
    "运营支持": ["运营", "客服", "支持", "协调", "行政", "人事"],
    "产品设计": ["产品经理", "ui", "ux", "设计", "交互", "原型"],
    # 商品/产品
    "手机数码": ["手机", "iphone", "galaxy", "pixel", "华为", "小米", "oppo", "vivo", "平板", "耳机"],
    "电脑硬件": ["电脑", "笔记本", "gpu", "cpu", "显卡", "内存", "ssd", "主板", "显示器", "rtx", "macbook"],
    "智能设备": ["智能手表", "手环", "音箱", "路由器", "摄像头", "无人机", "vr", "ar"],
    "汽车出行": ["汽车", "新能源", "电动车", "特斯拉", "比亚迪", "蔚来", "小鹏", "理想", "suv", "轿车"],
    "家居生活": ["家具", "家电", "厨房", "卫浴", "家居", "空调", "冰箱", "洗衣机"],
    "服饰美妆": ["服装", "鞋", "包", "化妆品", "护肤", "美妆"],
    # 新闻
    "科技资讯": ["科技", "互联网", "人工智能", "芯片", "5g", "区块链", "大模型", "chatgpt"],
    "财经新闻": ["股票", "基金", "理财", "金融", "经济", "gdp", "央行", "上市"],
    "社会民生": ["教育", "医疗", "房价", "就业", "社保", "养老", "政策"],
    # 学术
    "学术研究": ["论文", "研究", "实验", "算法", "模型", "数据集", "arxiv"],
}

PRIORITY_RULES: dict[str, list[str]] = {
    "高": ["急招", "核心", "重点", "高级", "热门", "爆款", "突发", "重磅", "独家", "首发", "旗舰", "顶级"],
    "中": ["推荐", "精选", "关注", "值得", "不错", "优秀", "主流"],
}

# ---------------------------------------------------------------------------
# 品牌识别
# ---------------------------------------------------------------------------
BRAND_MAP: dict[str, list[str]] = {
    "Apple": ["apple", "苹果", "iphone", "ipad", "macbook", "airpods", "apple watch"],
    "Samsung": ["samsung", "三星", "galaxy"],
    "Huawei": ["huawei", "华为", "mate", "nova", "pura", "鸿蒙"],
    "Xiaomi": ["xiaomi", "小米", "红米", "redmi", "poco"],
    "OPPO": ["oppo", "一加", "oneplus", "realme"],
    "vivo": ["vivo", "iqoo"],
    "Google": ["google", "pixel"],
    "NVIDIA": ["nvidia", "英伟达", "geforce", "rtx", "gtx"],
    "AMD": ["amd", "radeon", "ryzen", "锐龙"],
    "Intel": ["intel", "英特尔", "酷睿"],
    "Tesla": ["tesla", "特斯拉"],
    "BYD": ["byd", "比亚迪"],
    "Sony": ["sony", "索尼", "playstation", "ps5"],
    "Microsoft": ["microsoft", "微软", "xbox", "surface"],
}


def _detect_brand(text: str) -> str:
    lowered = text.lower()
    for brand, keywords in BRAND_MAP.items():
        if any(kw in lowered for kw in keywords):
            return brand
    return ""


# ---------------------------------------------------------------------------
# 情感倾向分析
# ---------------------------------------------------------------------------
_POSITIVE_WORDS = {
    "好", "优秀", "出色", "强大", "流畅", "惊艳", "值得", "推荐", "满意", "喜欢",
    "不错", "给力", "牛", "赞", "棒", "完美", "超值", "划算", "良心", "旗舰",
    "excellent", "great", "amazing", "best", "good", "love", "perfect",
}
_NEGATIVE_WORDS = {
    "差", "垃圾", "坑", "烂", "失望", "后悔", "卡顿", "发热", "缩水", "翻车",
    "不值", "太贵", "难用", "bug", "问题", "缺点", "不足", "槽点", "吐槽",
    "bad", "worst", "terrible", "poor", "disappointing", "overpriced",
}


def _detect_sentiment(text: str) -> str:
    lowered = text.lower()
    pos = sum(1 for w in _POSITIVE_WORDS if w in lowered)
    neg = sum(1 for w in _NEGATIVE_WORDS if w in lowered)
    if pos > neg + 1:
        return "正面"
    if neg > pos + 1:
        return "负面"
    return "中性"


# ---------------------------------------------------------------------------
# 通用工具
# ---------------------------------------------------------------------------
CITIES = [
    "北京", "上海", "广州", "深圳", "杭州", "苏州", "成都",
    "武汉", "南京", "西安", "重庆", "天津", "长沙", "郑州",
    "青岛", "大连", "厦门", "合肥", "珠海", "东莞", "佛山",
    "宁波", "无锡", "济南", "福州", "昆明", "贵阳", "海口",
]

STOPWORDS = {
    "负责", "以及", "相关", "熟悉", "能够", "工作", "岗位", "经验",
    "以上", "进行", "我们", "团队", "公司", "提供", "要求", "具有",
    "了解", "使用", "通过", "支持", "包括", "其他", "优秀", "可以",
    "需要", "一个", "这个", "那个", "什么", "如何", "怎么", "就是",
}


def _detect_category(text: str) -> str:
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
        if any(kw in lowered for kw in keywords):
            return label
    return "低"


def _detect_city(text: str) -> str:
    for city in CITIES:
        if city in text:
            return city
    return ""


def _extract_keywords(text: str, top_n: int = 5) -> str:
    words = re.findall(r"[A-Za-z]+[\d]*|[\u4e00-\u9fff]{2,}", text)
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


def _build_summary(record: dict[str, str], category: str, priority: str, sentiment: str) -> str:
    base = (
        record.get("snippet")
        or record.get("summary")
        or record.get("content")
        or record.get("abstract")
        or record.get("title", "")
    )
    base = base[:100] + ("…" if len(base) > 100 else "")
    parts = [category]
    brand = record.get("brand", "")
    if brand:
        parts.append(brand)
    parts.append(f"优先级{priority}")
    if sentiment != "中性":
        parts.append(sentiment)
    return " | ".join(parts) + f" | {base}"


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------
def tag_records(records: list[dict[str, str]]) -> list[dict[str, str]]:
    """对记录列表进行智能标签分类"""
    tagged: list[dict[str, str]] = []
    for record in records:
        merged_text = " ".join(
            str(record.get(field, ""))
            for field in [
                "title", "snippet", "summary", "content", "abstract",
                "company", "location", "specs", "price",
            ]
        )
        category = _detect_category(merged_text)
        priority = _detect_priority(merged_text)
        city = record.get("location") or _detect_city(merged_text)
        brand = _detect_brand(merged_text)
        sentiment = _detect_sentiment(merged_text)
        keywords = _extract_keywords(merged_text)

        tagged.append(
            {
                **record,
                "category": category,
                "priority": priority,
                "city": city,
                "brand": brand,
                "sentiment": sentiment,
                "keywords": keywords,
                "ai_summary": _build_summary(record, category, priority, sentiment),
            }
        )
    return tagged
