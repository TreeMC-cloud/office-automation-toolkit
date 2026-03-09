"""HTML 报告渲染 — Jinja2 + 自定义过滤器"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


def render_html_report(template_path: Path, context: dict) -> str:
    env = Environment(
        loader=FileSystemLoader(str(template_path.parent)),
        autoescape=select_autoescape(["html", "xml"]),
    )

    # 自定义过滤器
    env.filters["comma"] = _filter_comma
    env.filters["pct"] = _filter_pct

    template = env.get_template(template_path.name)
    return template.render(**context)


def _filter_comma(value, decimals: int = 2) -> str:
    """千分位格式化"""
    try:
        return f"{float(value):,.{decimals}f}"
    except (ValueError, TypeError):
        return str(value)


def _filter_pct(value, decimals: int = 1) -> str:
    """百分比格式化"""
    try:
        return f"{float(value):.{decimals}f}%"
    except (ValueError, TypeError):
        return str(value)
