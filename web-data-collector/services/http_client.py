from __future__ import annotations

from pathlib import Path
from urllib.parse import urljoin

import requests


DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (NarraFork Office Automation Demo)",
}


def fetch_html(source: str, timeout: int = 15) -> str:
    candidate = Path(source)
    if candidate.exists():
        return candidate.read_text(encoding="utf-8")
    response = requests.get(source, headers=DEFAULT_HEADERS, timeout=timeout)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


def resolve_link(link: str, base_url: str = "", local_base_dir=None) -> str:
    if not link:
        return ""
    if link.startswith(("http://", "https://")):
        return link
    if local_base_dir is not None:
        return str((Path(local_base_dir) / link).resolve())
    return urljoin(base_url, link)
