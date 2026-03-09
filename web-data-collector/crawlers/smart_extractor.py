"""智能正文提取 — 从 HTML 页面中提取结构化数据"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Comment, Tag


# ---------------------------------------------------------------------------
# 正文密度提取（基于文本密度算法）
# ---------------------------------------------------------------------------
_NOISE_TAGS = {"script", "style", "nav", "footer", "header", "aside", "iframe", "noscript", "form"}


def _extract_main_content(soup: BeautifulSoup) -> str:
    """使用文本密度算法提取页面主体正文"""
    # 移除噪声标签
    for tag in soup.find_all(_NOISE_TAGS):
        tag.decompose()
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    # 找到文本密度最高的块
    candidates: list[tuple[Tag, float]] = []
    for tag in soup.find_all(["div", "article", "section", "main", "td"]):
        text = tag.get_text(" ", strip=True)
        text_len = len(text)
        if text_len < 50:
            continue
        # 文本密度 = 文本长度 / (标签数 + 1)
        tag_count = len(tag.find_all(True))
        density = text_len / (tag_count + 1)
        candidates.append((tag, density))

    if not candidates:
        return soup.get_text(" ", strip=True)[:2000]

    # 按密度排序，取最高的
    candidates.sort(key=lambda x: x[1], reverse=True)
    best = candidates[0][0]
    return best.get_text("\n", strip=True)


# ---------------------------------------------------------------------------
# 字段提取正则
# ---------------------------------------------------------------------------
_PRICE_PATTERNS = [
    re.compile(r"[¥￥]\s*[\d,]+\.?\d*"),
    re.compile(r"\d[\d,]*\.?\d*\s*元"),
    re.compile(r"\$\s*[\d,]+\.?\d*"),
    re.compile(r"USD\s*[\d,]+\.?\d*", re.IGNORECASE),
]

_SALARY_PATTERNS = [
    re.compile(r"\d+[kK]-\d+[kK]"),
    re.compile(r"\d+\.?\d*万?-\d+\.?\d*万?/月"),
    re.compile(r"[\d.]+-[\d.]+万/年"),
    re.compile(r"月薪\s*[\d.]+-[\d.]+\s*[万千]?"),
    re.compile(r"年薪\s*[\d.]+-[\d.]+\s*万?"),
]

_DATE_PATTERNS = [
    re.compile(r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?"),
    re.compile(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}"),
    re.compile(r"\d{1,2}月\d{1,2}日"),
    re.compile(r"\d+\s*(?:小时|分钟|天|周)前"),
]

_AUTHOR_PATTERNS = [
    re.compile(r"(?:作者|记者|编辑|来源)[：:]\s*(\S+)"),
    re.compile(r"(?:by|author)[：:\s]+(\S+)", re.IGNORECASE),
]


def _find_first_match(text: str, patterns: list[re.Pattern]) -> str:
    """在文本中查找第一个匹配的模式"""
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return match.group(0) if not match.groups() else match.group(1)
    return ""


def _extract_meta(soup: BeautifulSoup, names: list[str]) -> str:
    """从 meta 标签中提取信息"""
    for name in names:
        tag = soup.find("meta", attrs={"name": name}) or soup.find("meta", attrs={"property": name})
        if tag and tag.get("content"):
            return tag["content"].strip()
    return ""


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------
def extract_page_content(html: str, expected_fields: list[str]) -> dict[str, str]:
    """
    根据期望字段，从 HTML 中智能提取结构化数据。

    Parameters
    ----------
    html : str
        页面 HTML 内容
    expected_fields : list[str]
        期望提取的字段列表

    Returns
    -------
    dict[str, str]
        提取到的字段值
    """
    soup = BeautifulSoup(html, "html.parser")
    result: dict[str, str] = {}

    # 提取页面标题
    if "title" in expected_fields:
        title_tag = soup.find("title")
        h1_tag = soup.find("h1")
        og_title = _extract_meta(soup, ["og:title", "twitter:title"])
        result["title"] = og_title or (h1_tag.get_text(" ", strip=True) if h1_tag else "") or (title_tag.get_text(" ", strip=True) if title_tag else "")

    # 提取正文
    full_text = _extract_main_content(soup)

    if "content" in expected_fields:
        result["content"] = full_text[:1500]  # 限制长度

    if "abstract" in expected_fields:
        # 论文摘要：优先从 meta 获取
        abstract = _extract_meta(soup, ["description", "og:description", "citation_abstract"])
        result["abstract"] = abstract or full_text[:500]

    # 提取来源
    if "source" in expected_fields:
        source = _extract_meta(soup, ["og:site_name", "application-name"])
        if not source:
            # 从 URL 或 domain 推断
            domain_tag = soup.find("meta", attrs={"property": "og:url"})
            source = domain_tag["content"] if domain_tag and domain_tag.get("content") else ""
        result["source"] = source

    # 提取日期
    if "publish_date" in expected_fields:
        date = _extract_meta(soup, [
            "article:published_time", "datePublished", "pubdate",
            "og:article:published_time", "date",
        ])
        if not date:
            date = _find_first_match(full_text, _DATE_PATTERNS)
        result["publish_date"] = date

    # 提取价格
    if "price" in expected_fields:
        result["price"] = _find_first_match(full_text, _PRICE_PATTERNS)

    # 提取薪资
    if "salary" in expected_fields:
        result["salary"] = _find_first_match(full_text, _SALARY_PATTERNS)

    # 提取作者
    if "author" in expected_fields or "authors" in expected_fields:
        author = _extract_meta(soup, ["author", "citation_author", "article:author"])
        if not author:
            author = _find_first_match(full_text, _AUTHOR_PATTERNS)
        field_name = "authors" if "authors" in expected_fields else "author"
        result[field_name] = author

    # 提取公司
    if "company" in expected_fields:
        company = _extract_meta(soup, ["og:site_name"])
        if not company:
            # 尝试从正文中匹配公司名
            company_match = re.search(r"(?:公司|企业|单位)[：:]\s*(\S+)", full_text)
            company = company_match.group(1) if company_match else ""
        result["company"] = company

    # 提取地点
    if "location" in expected_fields:
        location = ""
        location_match = re.search(
            r"(?:地[点址]|工作地|城市)[：:]\s*(\S+)", full_text
        )
        if location_match:
            location = location_match.group(1)
        result["location"] = location

    return result


def enrich_search_results(
    search_results: list[dict[str, str]],
    expected_fields: list[str],
    progress_callback=None,
) -> list[dict[str, str]]:
    """
    对搜索结果列表逐一访问原始页面并提取结构化数据。

    Parameters
    ----------
    search_results : list[dict[str, str]]
        搜索结果列表，每个元素包含 title, url, snippet
    expected_fields : list[str]
        期望提取的字段列表
    progress_callback : callable, optional
        进度回调 (current_index, total, url)

    Returns
    -------
    list[dict[str, str]]
        丰富后的记录列表
    """
    from services.http_client import fetch_html

    enriched: list[dict[str, str]] = []

    for i, item in enumerate(search_results):
        if progress_callback:
            progress_callback(i, len(search_results), item.get("url", ""))

        record: dict[str, str] = {
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("snippet", ""),
            "error": "",
        }

        url = item.get("url", "")
        if url:
            try:
                html = fetch_html(url, timeout=15)
                extracted = extract_page_content(html, expected_fields)
                # 用提取到的数据覆盖（但保留搜索结果中的 title 作为后备）
                for field, value in extracted.items():
                    if value:  # 只覆盖非空值
                        record[field] = value
                # 如果提取的 title 为空，保留搜索结果的 title
                if not record.get("title"):
                    record["title"] = item.get("title", "")
            except Exception as exc:
                record["error"] = str(exc)[:200]

        # 确保所有期望字段都存在
        for field in expected_fields:
            if field not in record:
                record[field] = ""

        enriched.append(record)

    return enriched
