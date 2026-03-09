"""多引擎搜索爬虫 — 支持 Bing、百度、搜狗，并发抓取，结果合并去重"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote_plus, unquote, urlparse, parse_qs

from bs4 import BeautifulSoup

from services.http_client import fetch_html, fetch_html_safe, extract_domain


# ---------------------------------------------------------------------------
# 搜索引擎解析器
# ---------------------------------------------------------------------------

def _parse_bing_results(html: str) -> list[dict[str, str]]:
    """解析 Bing 搜索结果"""
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict[str, str]] = []

    for item in soup.select("li.b_algo"):
        title_node = item.select_one("h2 a")
        snippet_node = item.select_one(".b_caption p, p")
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
            "search_engine": "Bing",
        })

    return results


def _parse_baidu_results(html: str) -> list[dict[str, str]]:
    """解析百度搜索结果"""
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict[str, str]] = []

    # 百度搜索结果容器
    for item in soup.select("div.result, div.c-container"):
        title_node = item.select_one("h3 a, .c-title a")
        snippet_node = item.select_one(
            ".c-abstract, .c-span-last, .content-right_8Zs40, div[class*='content']"
        )
        if not title_node:
            continue

        title = title_node.get_text(" ", strip=True)
        url = title_node.get("href", "")
        snippet = snippet_node.get_text(" ", strip=True) if snippet_node else ""

        if not url:
            continue

        results.append({
            "title": title,
            "url": url,
            "snippet": snippet,
            "search_engine": "百度",
        })

    return results


def _parse_sogou_results(html: str) -> list[dict[str, str]]:
    """解析搜狗搜索结果"""
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict[str, str]] = []

    for item in soup.select("div.vrwrap, div.rb"):
        title_node = item.select_one("h3 a, a[href]")
        snippet_node = item.select_one("p, .str_info, div.ft")
        if not title_node:
            continue

        title = title_node.get_text(" ", strip=True)
        url = title_node.get("href", "")
        snippet = snippet_node.get_text(" ", strip=True) if snippet_node else ""

        if not url:
            continue

        results.append({
            "title": title,
            "url": url,
            "snippet": snippet,
            "search_engine": "搜狗",
        })

    return results


# 引擎注册表
_ENGINE_PARSERS = {
    "bing": _parse_bing_results,
    "baidu": _parse_baidu_results,
    "sogou": _parse_sogou_results,
}

_ENGINE_URL_TEMPLATES = {
    "bing": "https://www.bing.com/search?q={query}&first={offset}&count=10",
    "baidu": "https://www.baidu.com/s?wd={query}&pn={offset}&rn=10",
    "sogou": "https://www.sogou.com/web?query={query}&page={page}",
}

_ENGINE_HEADERS = {
    "baidu": {"Referer": "https://www.baidu.com/"},
    "sogou": {"Referer": "https://www.sogou.com/"},
}


# ---------------------------------------------------------------------------
# 单引擎搜索
# ---------------------------------------------------------------------------
def search_single_engine(
    keyword: str,
    engine: str = "bing",
    max_results: int = 10,
) -> list[dict[str, str]]:
    """通过指定搜索引擎搜索关键词"""
    parser = _ENGINE_PARSERS.get(engine)
    if not parser:
        return []

    encoded = quote_plus(keyword)
    all_results: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for page in range(3):  # 最多 3 页
        if len(all_results) >= max_results:
            break

        if engine == "bing":
            url = _ENGINE_URL_TEMPLATES[engine].format(query=encoded, offset=page * 10 + 1)
        elif engine == "baidu":
            url = _ENGINE_URL_TEMPLATES[engine].format(query=encoded, offset=page * 10)
        else:  # sogou
            url = _ENGINE_URL_TEMPLATES[engine].format(query=encoded, page=page + 1)

        extra_headers = _ENGINE_HEADERS.get(engine)
        html = fetch_html_safe(url, timeout=20, extra_headers=extra_headers)
        if not html:
            break

        page_results = parser(html)
        if not page_results:
            break

        for result in page_results:
            result_url = result["url"]
            # 规范化 URL 用于去重
            domain = extract_domain(result_url)
            if result_url not in seen_urls:
                seen_urls.add(result_url)
                result["domain"] = domain
                all_results.append(result)
                if len(all_results) >= max_results:
                    break

        if page < 2:
            time.sleep(0.8)

    return all_results[:max_results]


# ---------------------------------------------------------------------------
# 多引擎并发搜索
# ---------------------------------------------------------------------------
def search_multi_engine(
    queries: list[str],
    engines: list[str] | None = None,
    max_results: int = 15,
    progress_callback=None,
) -> list[dict[str, str]]:
    """
    多引擎并发搜索，合并去重。

    Parameters
    ----------
    queries : list[str]
        搜索查询列表
    engines : list[str]
        搜索引擎列表
    max_results : int
        最终返回的最大结果数
    progress_callback : callable, optional
        进度回调 (message, progress_ratio)

    Returns
    -------
    list[dict[str, str]]
        合并去重后的结果列表，每条包含 title, url, snippet, search_engine, domain
    """
    if engines is None:
        engines = ["bing", "baidu"]

    # 构建所有搜索任务
    tasks: list[tuple[str, str]] = []
    for query in queries:
        for engine in engines:
            tasks.append((query, engine))

    all_results: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    completed = 0
    total = len(tasks)

    def _do_search(query: str, engine: str) -> list[dict[str, str]]:
        return search_single_engine(query, engine, max_results=max_results)

    # 并发执行（最多 4 个线程）
    with ThreadPoolExecutor(max_workers=min(4, total)) as executor:
        futures = {
            executor.submit(_do_search, query, engine): (query, engine)
            for query, engine in tasks
        }

        for future in as_completed(futures):
            query, engine = futures[future]
            completed += 1

            if progress_callback:
                progress_callback(
                    f"搜索 {engine}：{query[:30]}…",
                    completed / total,
                )

            try:
                results = future.result()
            except Exception:
                continue

            for result in results:
                url = result["url"]
                title = result["title"].strip()

                # 双重去重：URL + 标题
                title_key = title.lower()[:50]
                if url in seen_urls or title_key in seen_titles:
                    continue

                seen_urls.add(url)
                seen_titles.add(title_key)
                all_results.append(result)

    # 按来源多样性排序：交替不同引擎的结果
    all_results = _interleave_by_engine(all_results)

    return all_results[:max_results]


def _interleave_by_engine(results: list[dict[str, str]]) -> list[dict[str, str]]:
    """将不同引擎的结果交替排列，确保来源多样性"""
    by_engine: dict[str, list[dict[str, str]]] = {}
    for r in results:
        engine = r.get("search_engine", "unknown")
        by_engine.setdefault(engine, []).append(r)

    interleaved: list[dict[str, str]] = []
    engine_lists = list(by_engine.values())
    max_len = max((len(lst) for lst in engine_lists), default=0)

    for i in range(max_len):
        for lst in engine_lists:
            if i < len(lst):
                interleaved.append(lst[i])

    return interleaved
