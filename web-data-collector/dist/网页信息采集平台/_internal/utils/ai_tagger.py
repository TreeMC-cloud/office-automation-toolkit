from __future__ import annotations

import re


ROLE_RULES = {
    "后端开发": ["后端", "python", "java", "api", "服务端"],
    "前端开发": ["前端", "react", "vue", "小程序"],
    "数据分析": ["数据分析", "sql", "bi", "报表"],
    "运营支持": ["运营", "客服", "支持", "协调"],
}

PRIORITY_RULES = {
    "高": ["急招", "核心", "重点", "负责人", "高级"],
    "中": ["熟悉", "参与", "协助"],
}

CITIES = ["北京", "上海", "广州", "深圳", "杭州", "苏州", "成都"]
STOPWORDS = {"负责", "以及", "相关", "熟悉", "能够", "工作", "岗位", "经验", "以上", "进行", "我们", "团队"}


def _detect_role(text: str) -> str:
    lowered = text.lower()
    for label, keywords in ROLE_RULES.items():
        if any(keyword in lowered for keyword in keywords):
            return label
    return "综合信息"


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
    return "未识别"


def _extract_keywords(text: str, top_n: int = 5) -> str:
    words = re.findall(r"[A-Za-z]+|[一-鿿]{2,}", text)
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
    base = record.get("summary") or record.get("content") or record.get("title", "")
    base = base[:80] + ("..." if len(base) > 80 else "")
    return f"{category} | 优先级{priority} | {city} | {base}"


def tag_records(records: list[dict[str, str]]) -> list[dict[str, str]]:
    tagged: list[dict[str, str]] = []
    for record in records:
        merged_text = " ".join(
            str(record.get(field, ""))
            for field in ["title", "summary", "content", "company", "location"]
        )
        category = _detect_role(merged_text)
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
