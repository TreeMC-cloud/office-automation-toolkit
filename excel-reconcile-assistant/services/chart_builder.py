"""图表生成模块 — 输出 base64 PNG"""
from __future__ import annotations

import base64
import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False


def build_match_pie_base64(stats: dict) -> str:
    """匹配率饼图：完全匹配 / 字段不一致 / 未匹配"""
    exact = stats.get("exact_match_rows", 0)
    mismatch = stats.get("mismatch_rows", 0)
    unmatched = stats.get("missing_in_b_rows", 0) + stats.get("missing_in_a_rows", 0)

    labels = ["完全匹配", "字段不一致", "未匹配"]
    sizes = [exact, mismatch, unmatched]
    colors = ["#4CAF50", "#FFC107", "#F44336"]

    fig, ax = plt.subplots(figsize=(5, 4))
    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, colors=colors,
        autopct="%1.1f%%", startangle=90,
        textprops={"fontsize": 11},
    )
    for t in autotexts:
        t.set_fontsize(10)
    ax.set_title("匹配率分布", fontsize=14)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()


def build_diff_bar_base64(mismatch_details: pd.DataFrame) -> str:
    """差异分布柱状图：按字段名统计不一致数量"""
    if mismatch_details.empty or "字段A" not in mismatch_details.columns:
        # 空数据时返回占位图
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.text(0.5, 0.5, "无差异数据", ha="center", va="center", fontsize=14)
        ax.set_axis_off()
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=120)
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode()

    counts = mismatch_details["字段A"].value_counts()
    fields = counts.index.tolist()
    values = counts.values.tolist()

    fig, ax = plt.subplots(figsize=(max(6, len(fields) * 0.9), 4))
    bars = ax.bar(fields, values, color="#2196F3")
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                str(val), ha="center", va="bottom", fontsize=10)
    ax.set_xlabel("字段名", fontsize=12)
    ax.set_ylabel("不一致数量", fontsize=12)
    ax.set_title("差异分布", fontsize=14)
    plt.xticks(rotation=30, ha="right")
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()
