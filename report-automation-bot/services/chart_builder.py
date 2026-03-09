"""图表生成 — 折线/柱状/饼图，数据标签，双Y轴环比，自适应"""

from __future__ import annotations

import base64
import io

import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

# 配色方案
COLORS = ["#2563eb", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6",
          "#ec4899", "#06b6d4", "#84cc16", "#f97316", "#6366f1"]


def build_line_chart_base64(
    dataframe: pd.DataFrame, x_column: str, y_column: str, title: str,
    change_column: str | None = None,
) -> str:
    """折线图，可选叠加环比变化率（双 Y 轴）"""
    if dataframe.empty:
        return ""

    x = dataframe[x_column].astype(str).tolist()
    y = dataframe[y_column].astype(float).tolist()
    width = max(8, min(len(x) * 0.6, 16))
    fig, ax1 = plt.subplots(figsize=(width, 4.5))

    ax1.plot(x, y, marker="o", color=COLORS[0], linewidth=2, markersize=4, label=y_column)
    ax1.set_title(title, fontsize=14, fontweight="bold", pad=12)
    ax1.grid(axis="y", linestyle="--", alpha=0.3)
    ax1.set_ylabel(y_column, color=COLORS[0])

    # 数据标签（间隔显示，避免密集）
    step = max(1, len(x) // 12)
    for i in range(0, len(x), step):
        ax1.annotate(f"{y[i]:,.0f}", (x[i], y[i]), textcoords="offset points",
                     xytext=(0, 8), ha="center", fontsize=8, color=COLORS[0])

    # 环比变化率（双 Y 轴）
    if change_column and change_column in dataframe.columns:
        changes = dataframe[change_column].astype(float).tolist()
        ax2 = ax1.twinx()
        ax2.bar(x, changes, alpha=0.25, color=COLORS[3], width=0.6, label="环比变化率")
        ax2.set_ylabel("环比变化率 (%)", color=COLORS[3])
        ax2.tick_params(axis="y", labelcolor=COLORS[3])
        ax2.axhline(y=0, color="gray", linewidth=0.5, linestyle="--")

    _auto_xticks(ax1, x)
    fig.tight_layout()
    return _fig_to_base64(fig)


def build_bar_chart_base64(
    dataframe: pd.DataFrame, x_column: str, y_column: str, title: str,
) -> str:
    """柱状图 + 数据标签"""
    if dataframe.empty:
        return ""

    x = dataframe[x_column].astype(str).tolist()
    y = dataframe[y_column].astype(float).tolist()
    colors = [COLORS[i % len(COLORS)] for i in range(len(x))]

    fig, ax = plt.subplots(figsize=(max(6, len(x) * 0.8), 4.5))
    bars = ax.bar(x, y, color=colors, width=0.6)
    ax.set_title(title, fontsize=14, fontweight="bold", pad=12)
    ax.grid(axis="y", linestyle="--", alpha=0.3)

    # 数据标签
    for bar, val in zip(bars, y):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                f"{val:,.0f}", ha="center", va="bottom", fontsize=9)

    _auto_xticks(ax, x)
    fig.tight_layout()
    return _fig_to_base64(fig)


def build_pie_chart_base64(
    dataframe: pd.DataFrame, label_column: str, value_column: str, title: str,
) -> str:
    """饼图（维度占比）"""
    if dataframe.empty:
        return ""

    labels = dataframe[label_column].astype(str).tolist()
    values = dataframe[value_column].astype(float).tolist()
    colors = [COLORS[i % len(COLORS)] for i in range(len(labels))]

    fig, ax = plt.subplots(figsize=(7, 5))
    wedges, texts, autotexts = ax.pie(
        values, labels=labels, colors=colors, autopct="%1.1f%%",
        startangle=90, pctdistance=0.75,
    )
    for t in autotexts:
        t.set_fontsize(9)
    ax.set_title(title, fontsize=14, fontweight="bold", pad=12)
    fig.tight_layout()
    return _fig_to_base64(fig)


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------

def _auto_xticks(ax, labels: list) -> None:
    """X 轴标签自适应：数据多时间隔显示"""
    n = len(labels)
    if n > 20:
        step = max(1, n // 10)
        ax.set_xticks(range(0, n, step))
        ax.set_xticklabels([labels[i] for i in range(0, n, step)], rotation=30, ha="right", fontsize=9)
    elif n > 8:
        ax.tick_params(axis="x", rotation=30, labelsize=9)
    else:
        ax.tick_params(axis="x", rotation=0, labelsize=10)


def _fig_to_base64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("utf-8")
