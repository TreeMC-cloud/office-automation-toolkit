"""智能正文提取 — JSON-LD 结构化数据、多价格/多规格提取、图片采集、域名来源识别、质量评分"""

from __future__ import annotations

import json
import re
import time
from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup, Comment, Tag


# ---------------------------------------------------------------------------
# 噪声标签
# ---------------------------------------------------------------------------
_NOISE_TAGS = {
    "script", "style", "nav", "footer", "header", "aside",
    "iframe", "noscript", "form", "svg", "canvas",
}


# ---------------------------------------------------------------------------
# JSON-LD 结构化数据提取
# ---------------------------------------------------------------------------
def _extract_jsonld(soup: BeautifulSoup) -> list[dict]:
    """提取页面中的 JSON-LD 结构化数据"""
    results = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, list):
                results.extend(data)
            elif isinstance(data, dict):
                results.append(data)
        except (json.JSONDecodeError, TypeError):
            continue
    return results


def _extract_from_jsonld(jsonld_list: list[dict], expected_fields: list[str]) -> dict[str, str]:
    """从 JSON-LD 数据中提取字段"""
    result: dict[str, str] = {}

    for data in jsonld_list:
        schema_type = data.get("@type", "")
        if isinstance(schema_type, list):
            schema_type = schema_type[0] if schema_type else ""

        # 标题
        if "title" in expected_fields and not result.get("title"):
            result["title"] = str(data.get("name") or data.get("headline") or "")

        # 价格（Product 类型）
        if "price" in expected_fields and not result.get("price"):
            offers = data.get("offers", {})
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            price = offers.get("price") or offers.get("lowPrice") or data.get("price")
            currency = offers.get("priceCurrency", "")
            if price:
                result["price"] = f"{currency}{price}" if currency else str(price)

        # 规格
        if "specs" in expected_fields and not result.get("specs"):
            desc = data.get("description", "")
            if desc and len(str(desc)) > 10:
                result["specs"] = str(desc)[:500]

        # 日期
        if "publish_date" in expected_fields and not result.get("publish_date"):
            date = data.get("datePublished") or data.get("dateCreated") or data.get("dateModified")
            if date:
                result["publish_date"] = str(date)[:20]

        # 作者
        if ("author" in expected_fields or "authors" in expected_fields) and not result.get("author"):
            author = data.get("author", {})
            if isinstance(author, dict):
                author = author.get("name", "")
            elif isinstance(author, list):
                author = ", ".join(a.get("name", str(a)) if isinstance(a, dict) else str(a) for a in author)
            field_name = "authors" if "authors" in expected_fields else "author"
            result[field_name] = str(author)

        # 图片（从 JSON-LD 提取）
        if "image_url" in expected_fields and not result.get("image_url"):
            image = data.get("image") or data.get("thumbnailUrl") or ""
            if isinstance(image, list):
                image = image[0] if image else ""
            if isinstance(image, dict):
                image = image.get("url") or image.get("contentUrl") or ""
            if image and isinstance(image, str):
                result["image_url"] = image

        # 来源
        if "source" in expected_fields and not result.get("source"):
            publisher = data.get("publisher", {})
            if isinstance(publisher, dict):
                result["source"] = publisher.get("name", "")

    return result


# ---------------------------------------------------------------------------
# 正文密度提取（增强版）
# ---------------------------------------------------------------------------
def _clean_soup(soup: BeautifulSoup) -> BeautifulSoup:
    """清理噪声标签"""
    for tag in soup.find_all(_NOISE_TAGS):
        tag.decompose()
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()
    return soup


def _extract_main_content(soup: BeautifulSoup) -> str:
    """使用文本密度算法提取页面主体正文"""
    candidates: list[tuple[Tag, float]] = []
    for tag in soup.find_all(["div", "article", "section", "main", "td", "p"]):
        text = tag.get_text(" ", strip=True)
        text_len = len(text)
        if text_len < 30:
            continue
        tag_count = len(tag.find_all(True))
        link_count = len(tag.find_all("a"))
        # 文本密度 = 文本长度 / (标签数 + 1)，惩罚链接密集区域
        density = text_len / (tag_count + 1) * (1 - link_count / (tag_count + 1))
        candidates.append((tag, density))

    if not candidates:
        return soup.get_text(" ", strip=True)[:2000]

    candidates.sort(key=lambda x: x[1], reverse=True)
    best = candidates[0][0]
    return best.get_text("\n", strip=True)


# ---------------------------------------------------------------------------
# 字段提取正则（增强版）
# ---------------------------------------------------------------------------
_PRICE_PATTERNS = [
    re.compile(r"[¥￥]\s*[\d,]+\.?\d*"),
    re.compile(r"\d[\d,]*\.?\d*\s*元"),
    re.compile(r"\$\s*[\d,]+\.?\d*"),
    re.compile(r"(?:售价|定价|报价|到手价|起售价|官方价)[：:]*\s*[\d¥￥$,]+\.?\d*\s*元?"),
    re.compile(r"(?:price|cost)[：:\s]*\$?\s*[\d,]+\.?\d*", re.IGNORECASE),
]

_ALL_PRICES_PATTERN = re.compile(
    r"(?:[¥￥$]\s*[\d,]+\.?\d*|\d[\d,]*\.?\d*\s*元|(?:售价|定价|报价|到手价)[：:]*\s*[\d¥￥$,]+\.?\d*\s*元?)"
)

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
    re.compile(r"(?:作者|记者|编辑|来源|文)[：:/|]\s*(\S+)"),
    re.compile(r"(?:by|author)[：:\s]+(\S+)", re.IGNORECASE),
]

# 规格参数提取
_SPEC_PATTERNS = [
    re.compile(r"(?:处理器|芯片|CPU)[：:]\s*(.+?)(?:\n|$)"),
    re.compile(r"(?:内存|RAM)[：:]\s*(.+?)(?:\n|$)"),
    re.compile(r"(?:存储|ROM|容量)[：:]\s*(.+?)(?:\n|$)"),
    re.compile(r"(?:屏幕|显示屏)[：:]\s*(.+?)(?:\n|$)"),
    re.compile(r"(?:电池|续航)[：:]\s*(.+?)(?:\n|$)"),
    re.compile(r"(?:摄像头|相机|镜头)[：:]\s*(.+?)(?:\n|$)"),
    re.compile(r"(?:尺寸|重量|厚度)[：:]\s*(.+?)(?:\n|$)"),
]


def _find_first_match(text: str, patterns: list[re.Pattern]) -> str:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return match.group(0) if not match.groups() else match.group(1)
    return ""


def _find_all_prices(text: str) -> list[str]:
    """提取文本中所有价格"""
    return list(set(_ALL_PRICES_PATTERN.findall(text)))[:5]


def _extract_specs(text: str) -> str:
    """提取规格参数"""
    specs = []
    for pattern in _SPEC_PATTERNS:
        match = pattern.search(text)
        if match:
            specs.append(match.group(0).strip())
    return " | ".join(specs) if specs else ""


def _extract_meta(soup: BeautifulSoup, names: list[str]) -> str:
    for name in names:
        tag = soup.find("meta", attrs={"name": name}) or soup.find("meta", attrs={"property": name})
        if tag and tag.get("content"):
            return tag["content"].strip()
    return ""


# ---------------------------------------------------------------------------
# 图片提取
# ---------------------------------------------------------------------------
_NOISE_IMAGE_PATTERNS = re.compile(
    r"(?:logo|icon|avatar|badge|sprite|pixel|tracking|ad[_-]|banner[_-]|button|arrow|spacer|blank|loading|spinner)",
    re.IGNORECASE,
)

_MIN_IMAGE_SIZE = 100  # 最小宽/高像素（过滤小图标）


def _is_valid_image_url(url: str) -> bool:
    """判断是否为有效的产品/内容图片 URL"""
    if not url or len(url) < 10:
        return False
    # 必须是 http(s) 或 // 开头
    if not url.startswith(("http://", "https://", "//")):
        return False
    # 排除噪声图片
    if _NOISE_IMAGE_PATTERNS.search(url):
        return False
    # 排除 data URI
    if url.startswith("data:"):
        return False
    # 排除 SVG（通常是图标）
    if url.lower().endswith(".svg"):
        return False
    return True


def _extract_images(soup: BeautifulSoup, page_url: str = "", max_images: int = 5) -> list[str]:
    """
    从页面中提取产品/内容相关图片 URL。

    优先级：
    1. og:image / twitter:image（社交分享图，通常是主图）
    2. JSON-LD 中的 image（已在 _extract_from_jsonld 处理）
    3. 正文区域的大图（img 标签，按尺寸和位置排序）
    """
    images: list[str] = []
    seen: set[str] = set()

    def _add(url: str) -> bool:
        if not url:
            return False
        # 补全协议
        if url.startswith("//"):
            url = "https:" + url
        elif not url.startswith("http") and page_url:
            url = urljoin(page_url, url)
        if not _is_valid_image_url(url):
            return False
        normalized = url.split("?")[0].lower()  # 去参数去重
        if normalized in seen:
            return False
        seen.add(normalized)
        images.append(url)
        return True

    # 1. og:image / twitter:image
    for meta_name in ["og:image", "og:image:url", "twitter:image", "twitter:image:src"]:
        tag = soup.find("meta", attrs={"property": meta_name}) or soup.find("meta", attrs={"name": meta_name})
        if tag and tag.get("content"):
            _add(tag["content"].strip())

    # 2. 正文区域的 img 标签
    # 优先在 article/main/正文容器中找
    content_areas = soup.find_all(["article", "main", "section"])
    if not content_areas:
        content_areas = [soup.body] if soup.body else [soup]

    for area in content_areas:
        for img in area.find_all("img", src=True):
            src = img.get("src", "")
            # data-src 懒加载
            lazy_src = img.get("data-src") or img.get("data-original") or img.get("data-lazy-src") or ""
            actual_src = lazy_src or src

            # 尺寸过滤
            width = img.get("width", "")
            height = img.get("height", "")
            try:
                w = int(str(width).replace("px", "").strip()) if width else 0
                h = int(str(height).replace("px", "").strip()) if height else 0
                if (w > 0 and w < _MIN_IMAGE_SIZE) or (h > 0 and h < _MIN_IMAGE_SIZE):
                    continue
            except (ValueError, TypeError):
                pass

            _add(actual_src)

            if len(images) >= max_images:
                break
        if len(images) >= max_images:
            break

    return images[:max_images]


# ---------------------------------------------------------------------------
# 质量评分
# ---------------------------------------------------------------------------
def _score_record(record: dict[str, str], expected_fields: list[str]) -> int:
    """对提取结果打分（0-100），衡量信息完整度"""
    if not expected_fields:
        return 50

    filled = 0
    total = len(expected_fields)

    for field in expected_fields:
        value = record.get(field, "").strip()
        if value and value not in ("", "未知", "N/A"):
            filled += 1

    # 基础分
    base_score = int(filled / total * 80)

    # 加分项
    bonus = 0
    if record.get("title", "").strip():
        bonus += 10
    content = record.get("content") or record.get("abstract") or record.get("snippet", "")
    if len(content) > 100:
        bonus += 10

    return min(100, base_score + bonus)


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------
def extract_page_content(html: str, expected_fields: list[str]) -> dict[str, str]:
    """根据期望字段，从 HTML 中智能提取结构化数据"""
    soup = BeautifulSoup(html, "html.parser")
    result: dict[str, str] = {}

    # 1. 优先从 JSON-LD 提取
    jsonld_list = _extract_jsonld(soup)
    if jsonld_list:
        result = _extract_from_jsonld(jsonld_list, expected_fields)

    # 2. 清理噪声后提取正文
    soup = _clean_soup(soup)
    full_text = _extract_main_content(soup)

    # 3. 逐字段补充（JSON-LD 未覆盖的）
    if "title" in expected_fields and not result.get("title"):
        h1_tag = soup.find("h1")
        og_title = _extract_meta(soup, ["og:title", "twitter:title"])
        title_tag = soup.find("title")
        result["title"] = (
            og_title
            or (h1_tag.get_text(" ", strip=True) if h1_tag else "")
            or (title_tag.get_text(" ", strip=True) if title_tag else "")
        )

    if "content" in expected_fields and not result.get("content"):
        result["content"] = full_text[:2000]

    if "abstract" in expected_fields and not result.get("abstract"):
        abstract = _extract_meta(soup, ["description", "og:description", "citation_abstract"])
        result["abstract"] = abstract or full_text[:500]

    if "source" in expected_fields and not result.get("source"):
        result["source"] = _extract_meta(soup, ["og:site_name", "application-name"])

    if "publish_date" in expected_fields and not result.get("publish_date"):
        date = _extract_meta(soup, [
            "article:published_time", "datePublished", "pubdate",
            "og:article:published_time", "date",
        ])
        if not date:
            date = _find_first_match(full_text, _DATE_PATTERNS)
        result["publish_date"] = date

    if "price" in expected_fields and not result.get("price"):
        prices = _find_all_prices(full_text)
        result["price"] = prices[0] if prices else ""
        if len(prices) > 1:
            result["price_range"] = " ~ ".join(prices[:3])

    if "salary" in expected_fields and not result.get("salary"):
        result["salary"] = _find_first_match(full_text, _SALARY_PATTERNS)

    if ("author" in expected_fields or "authors" in expected_fields) and not result.get("author") and not result.get("authors"):
        author = _extract_meta(soup, ["author", "citation_author", "article:author"])
        if not author:
            author = _find_first_match(full_text, _AUTHOR_PATTERNS)
        field_name = "authors" if "authors" in expected_fields else "author"
        result[field_name] = author

    if "company" in expected_fields and not result.get("company"):
        company = _extract_meta(soup, ["og:site_name"])
        if not company:
            company_match = re.search(r"(?:公司|企业|单位|机构)[：:]\s*(\S+)", full_text)
            company = company_match.group(1) if company_match else ""
        result["company"] = company

    if "location" in expected_fields and not result.get("location"):
        location_match = re.search(r"(?:地[点址]|工作地|城市|所在地)[：:]\s*(\S+)", full_text)
        result["location"] = location_match.group(1) if location_match else ""

    if "specs" in expected_fields and not result.get("specs"):
        result["specs"] = _extract_specs(full_text)

    # 图片提取
    if "image_url" in expected_fields and not result.get("image_url"):
        images = _extract_images(soup)
        if images:
            result["image_url"] = images[0]  # 主图
            if len(images) > 1:
                result["image_urls"] = " | ".join(images[:5])  # 多图

    return result


def enrich_search_results(
    search_results: list[dict[str, str]],
    expected_fields: list[str],
    progress_callback=None,
    cancel_event=None,
    max_workers: int = 5,
) -> list[dict[str, str]]:
    """
    对搜索结果并发访问详情页，提取结构化内容。

    Parameters
    ----------
    cancel_event : threading.Event, optional
        取消信号，set 后停止采集
    max_workers : int
        并发线程数
    """
    import random
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from services.http_client import fetch_html, extract_domain

    total = len(search_results)
    enriched: list[dict[str, str]] = []
    lock = threading.Lock()
    counter = [0]  # mutable counter for thread-safe increment

    def _process_one(item: dict) -> dict[str, str]:
        if cancel_event and cancel_event.is_set():
            return {}

        record: dict[str, str] = {
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("snippet", ""),
            "search_engine": item.get("search_engine", ""),
            "domain": item.get("domain") or extract_domain(item.get("url", "")),
            "error": "",
        }

        url = item.get("url", "")
        if url:
            try:
                # 随机延迟避免被封
                time.sleep(random.uniform(0.2, 0.6))
                if cancel_event and cancel_event.is_set():
                    return {}
                html = fetch_html(url, timeout=12)
                extracted = extract_page_content(html, expected_fields)
                for field, value in extracted.items():
                    if value:
                        record[field] = value
                if not record.get("title"):
                    record["title"] = item.get("title", "")
                if not record.get("source") and "source" in expected_fields:
                    record["source"] = record["domain"]
            except Exception as exc:
                record["error"] = str(exc)[:200]

        for field in expected_fields:
            if field not in record:
                record[field] = ""

        record["quality_score"] = str(_score_record(record, expected_fields))

        with lock:
            counter[0] += 1
            if progress_callback:
                progress_callback(counter[0], total, url)

        return record

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_process_one, item): item for item in search_results}
        for future in as_completed(futures):
            if cancel_event and cancel_event.is_set():
                pool.shutdown(wait=False, cancel_futures=True)
                break
            result = future.result()
            if result:
                enriched.append(result)

    enriched.sort(key=lambda r: int(r.get("quality_score", "0")), reverse=True)
    return enriched


def download_images(
    records: list[dict],
    output_dir: str,
    cancel_event=None,
    progress_callback=None,
    max_workers: int = 5,
) -> int:
    """批量下载采集到的图片到本地文件夹，返回下载成功数"""
    import hashlib
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from services.http_client import fetch_html
    from pathlib import Path
    from urllib.request import urlopen, Request

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # 收集所有图片 URL
    image_tasks: list[tuple[str, str]] = []  # (url, record_title)
    for rec in records:
        title = rec.get("title", "untitled")[:30]
        main_img = rec.get("image_url", "")
        if main_img:
            image_tasks.append((main_img, title))
        multi = rec.get("image_urls", "")
        if multi:
            for u in multi.split("|"):
                u = u.strip()
                if u and u != main_img:
                    image_tasks.append((u, title))

    if not image_tasks:
        return 0

    total = len(image_tasks)
    success = [0]
    lock = threading.Lock()

    def _download_one(url: str, title: str) -> bool:
        if cancel_event and cancel_event.is_set():
            return False
        try:
            ext = ".jpg"
            for e in (".png", ".webp", ".gif", ".jpeg", ".jpg"):
                if e in url.lower():
                    ext = e
                    break
            name_hash = hashlib.md5(url.encode()).hexdigest()[:12]
            safe_title = "".join(c for c in title if c.isalnum() or c in " _-")[:20].strip()
            filename = f"{safe_title}_{name_hash}{ext}"

            req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(req, timeout=15) as resp:
                data = resp.read()
                if len(data) < 1000:  # 太小，可能不是真图片
                    return False
                (out / filename).write_bytes(data)

            with lock:
                success[0] += 1
                if progress_callback:
                    progress_callback(success[0], total)
            return True
        except Exception:
            return False

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(_download_one, url, title) for url, title in image_tasks]
        for f in as_completed(futures):
            if cancel_event and cancel_event.is_set():
                pool.shutdown(wait=False, cancel_futures=True)
                break

    return success[0]
