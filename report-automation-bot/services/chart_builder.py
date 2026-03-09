from __future__ import annotations

import base64
import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def _build_chart(dataframe: pd.DataFrame, x_column: str, y_column: str, title: str, chart_type: str) -> str:
    if dataframe.empty:
        return ""
    fig, ax = plt.subplots(figsize=(8, 4))
    x_values = dataframe[x_column].astype(str).tolist()
    y_values = dataframe[y_column].astype(float).tolist()
    if chart_type == "line":
        ax.plot(x_values, y_values, marker="o", color="#2563eb")
    else:
        ax.bar(x_values, y_values, color="#10b981")
    ax.set_title(title)
    ax.tick_params(axis="x", rotation=30)
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    figure_buffer = io.BytesIO()
    fig.tight_layout()
    fig.savefig(figure_buffer, format="png", dpi=150)
    plt.close(fig)
    return base64.b64encode(figure_buffer.getvalue()).decode("utf-8")


def build_line_chart_base64(dataframe: pd.DataFrame, x_column: str, y_column: str, title: str) -> str:
    return _build_chart(dataframe, x_column, y_column, title, chart_type="line")


def build_bar_chart_base64(dataframe: pd.DataFrame, x_column: str, y_column: str, title: str) -> str:
    return _build_chart(dataframe, x_column, y_column, title, chart_type="bar")
