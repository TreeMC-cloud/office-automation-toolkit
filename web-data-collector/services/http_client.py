"""HTTP 客户端 — 真实浏览器 UA 轮换、重试机制、编码增强"""

from __future__ import annotations

import random
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------------------------------------------------------------------------
# 真实浏览器 User-Agent 池
# ---------------------------------------------------------------------------
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 OPR/115.0.0.0",
]


def _random_ua() -> str:
    return random.choice(_USER_AGENTS)


def _build_headers(extra_headers: dict[str, str] | None = None) -> dict[str, str]:
    headers = {
        "User-Agent": _random_ua(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    if extra_headers:
        headers.update(extra_headers)
    return headers


# ---------------------------------------------------------------------------
# 带重试的 Session
# ---------------------------------------------------------------------------
def _create_session(max_retries: int = 3) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=max_retries,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


# 全局复用 session
_session = _create_session()


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------
def fetch_html(
    source: str,
    timeout: int = 15,
    extra_headers: dict[str, str] | None = None,
) -> str:
    """
    获取 HTML 内容。支持本地文件和远程 URL。

    - 自动轮换 User-Agent
    - 自动重试（429/5xx）
    - 智能编码检测
    """
    # 本地文件
    candidate = Path(source)
    if candidate.exists():
        return candidate.read_text(encoding="utf-8")

    headers = _build_headers(extra_headers)
    response = _session.get(source, headers=headers, timeout=timeout, allow_redirects=True)
    response.raise_for_status()

    # 智能编码：优先 apparent_encoding，回退 utf-8
    if response.apparent_encoding:
        response.encoding = response.apparent_encoding
    elif response.encoding and response.encoding.lower() in ("iso-8859-1", "latin-1"):
        response.encoding = "utf-8"

    return response.text


def fetch_html_safe(
    url: str,
    timeout: int = 12,
    extra_headers: dict[str, str] | None = None,
) -> str:
    """安全版本 — 出错返回空字符串而非抛异常"""
    try:
        return fetch_html(url, timeout=timeout, extra_headers=extra_headers)
    except Exception:
        return ""


def extract_domain(url: str) -> str:
    """从 URL 提取域名（去掉 www. 前缀）"""
    try:
        host = urlparse(url).netloc
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def resolve_link(link: str, base_url: str = "", local_base_dir=None) -> str:
    if not link:
        return ""
    if link.startswith(("http://", "https://")):
        return link
    if local_base_dir is not None:
        return str((Path(local_base_dir) / link).resolve())
    return urljoin(base_url, link)
