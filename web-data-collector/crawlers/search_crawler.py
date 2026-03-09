"""搜索引擎结果解析 — 抓取 Bing 搜索结果页并提取结果列表"""

from __future__ import annotations

import time
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from services.http_client import fetch_html


# Bing 搜索结果的常见选择器
_BING_RESULT_SELECTOR = "li.b_algo"
_BING_TITLE_SELECTOR = "h2 a"
_BING_SNIPPET_SELECTOR = ".b_caption p"


def _parse_bing_results(html: str) -> list[dict[str, str]]:
    """从 Bing 搜索结果页 HTML 中提取结果列表"""
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select(_BING_RESULT_SELECTOR)
    results: list[dict[str, str]] = []

    for item in items:
        title_node = item.select_one(_BING_TITLE_SELECTOR)
        snippet_node = item.select_one(_BING_SNIPPET_SELECTOR)

        if not title_node:
            continue

        title = title_node.get_text(" ", strip=True)
        url = title_node.get("href", "")
        snippet = snippet_node.get_text(" ", strip=True) if snippet_node else ""

        if not url or not url.startswith("http"):
            continue

        results.append({
            "title": title,
            "url": url,
            "snippet": snippet,
        })

    return results


def search_bing(keyword: str, max_results: int = 10) -> list[dict[str, str]]:
    """
    通过 Bing 搜索关键词并返回结果列表。

    Parameters
    ----------
    keyword : str
        搜索关键词
    max_results : int
        最大返回结果数

    Returns
    -------
    list[dict[str, str]]
        每个元素包含 title, url, snippet
    """
    encoded = quote_plus(keyword)
    all_results: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    # 分页抓取，每页最多 10 条
    page = 0
    while len(all_results) < max_results:
        offset = page * 10
        url = f"https://www.bing.com/search?q={encoded}&first={offset + 1}&count=10"

        try:
            html = fetch_html(url, timeout=20)
            page_results = _parse_bing_results(html)
        except Exception:
            break

        if not page_results:
            break

        for result in page_results:
            if result["url"] not in seen_urls:
                seen_urls.add(result["url"])
                all_results.append(result)
                if len(all_results) >= max_results:
                    break

        page += 1
        if page >= 3:  # 最多翻 3 页
            break

        time.sleep(0.5)  # 礼貌延迟

    return all_results[:max_results]


def search_multiple_queries(
    queries: list[str],
    max_results: int = 10,
    progress_callback=None,
) -> list[dict[str, str]]:
    """
    对多个查询执行搜索并合并去重结果。

    Parameters
    ----------
    queries : list[str]
        搜索查询列表
    max_results : int
        最终返回的最大结果数
    progress_callback : callable, optional
        进度回调 (current_query, query_index, total_queries)

    Returns
    -------
    list[dict[str, str]]
        合并去重后的结果列表
    """
    all_results: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for i, query in enumerate(queries):
        if progress_callback:
            progress_callback(query, i, len(queries))

        results = search_bing(query, max_results=max_results)

        for result in results:
            if result["url"] not in seen_urls:
                seen_urls.add(result["url"])
                all_results.append(result)

        if len(all_results) >= max_results:
            break

        if i < len(queries) - 1:
            time.sleep(1)  # 查询间延迟

    return all_results[:max_results]
