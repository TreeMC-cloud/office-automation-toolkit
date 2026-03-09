from __future__ import annotations

from bs4 import BeautifulSoup

from services.http_client import fetch_html


def _extract_text(soup: BeautifulSoup, selector: str, default: str = "") -> str:
    if not selector:
        return default
    node = soup.select_one(selector)
    return node.get_text(" ", strip=True) if node else default


def enrich_with_detail(
    records: list[dict[str, str]],
    content_selector: str,
    company_selector: str,
    location_selector: str,
    base_url: str = "",
    local_base_dir=None,
) -> list[dict[str, str]]:
    enriched: list[dict[str, str]] = []
    for record in records:
        content = ""
        company = record.get("company", "")
        location = record.get("location", "")
        error_message = ""
        url = record.get("url", "")
        try:
            if url:
                html = fetch_html(url)
                soup = BeautifulSoup(html, "html.parser")
                content = _extract_text(soup, content_selector)
                company = _extract_text(soup, company_selector, company)
                location = _extract_text(soup, location_selector, location)
        except Exception as exc:
            error_message = str(exc)
        enriched.append(
            {
                **record,
                "company": company,
                "location": location,
                "content": content,
                "error": error_message,
            }
        )
    return enriched
