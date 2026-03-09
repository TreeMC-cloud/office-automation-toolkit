from __future__ import annotations

from bs4 import BeautifulSoup

from services.http_client import resolve_link


def extract_list_items(
    html: str,
    item_selector: str,
    title_selector: str,
    link_selector: str,
    summary_selector: str = "",
    date_selector: str = "",
    base_url: str = "",
    local_base_dir=None,
) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select(item_selector) if item_selector else soup.select("article, li")
    records: list[dict[str, str]] = []
    for index, item in enumerate(items, start=1):
        title_node = item.select_one(title_selector) if title_selector else item.select_one("a[href]")
        link_node = item.select_one(link_selector) if link_selector else title_node
        summary_node = item.select_one(summary_selector) if summary_selector else None
        date_node = item.select_one(date_selector) if date_selector else None

        title = title_node.get_text(" ", strip=True) if title_node else ""
        href = link_node.get("href", "") if link_node else ""
        summary = summary_node.get_text(" ", strip=True) if summary_node else ""
        publish_date = date_node.get_text(" ", strip=True) if date_node else ""
        if not title:
            continue
        records.append(
            {
                "index": str(index),
                "title": title,
                "url": resolve_link(href, base_url=base_url, local_base_dir=local_base_dir),
                "summary": summary,
                "publish_date": publish_date,
            }
        )
    return records
