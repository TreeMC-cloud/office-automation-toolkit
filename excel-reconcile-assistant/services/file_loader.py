"""文件加载 — 支持 Excel / CSV，自动编码检测，保留 NaN 语义"""

from __future__ import annotations

from pathlib import Path
from typing import IO

import pandas as pd


def list_sheets(source) -> list[str]:
    """返回 Excel 文件的 Sheet 列表；CSV 返回 ['Sheet1']"""
    path = _resolve_path(source)
    if path.suffix.lower() == ".csv":
        return ["Sheet1"]
    xls = pd.ExcelFile(path)
    return xls.sheet_names


def read_dataframe(source, sheet_name: str | None = None) -> pd.DataFrame:
    """读取文件为 DataFrame，自动清洗但保留 NaN"""
    path = _resolve_path(source)
    ext = path.suffix.lower()

    if ext == ".csv":
        df = _read_csv(path)
    elif ext in (".xlsx", ".xls"):
        df = pd.read_excel(path, sheet_name=sheet_name or 0)
    else:
        raise ValueError(f"不支持的文件格式：{ext}")

    return _clean_dataframe(df)


# ---------------------------------------------------------------------------
# 内部函数
# ---------------------------------------------------------------------------

def _resolve_path(source) -> Path:
    """统一处理路径字符串、Path 对象、Streamlit UploadedFile"""
    if isinstance(source, (str, Path)):
        return Path(source)
    # Streamlit UploadedFile 或类文件对象
    if hasattr(source, "name"):
        return Path(source.name)
    raise TypeError(f"无法识别的文件来源类型：{type(source)}")


def _read_csv(path: Path) -> pd.DataFrame:
    """尝试多种编码读取 CSV"""
    encodings = ["utf-8-sig", "utf-8", "gbk", "gb18030", "latin-1"]
    for enc in encodings:
        try:
            return pd.read_csv(path, encoding=enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise ValueError(f"无法识别文件编码：{path.name}")


def _clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """基础清洗：去空行/空列、strip 文本，但保留 NaN"""
    # 去除全空行和全空列
    df = df.dropna(how="all").dropna(axis=1, how="all")

    # 文本列 strip（不 fillna，保留 NaN 语义）
    for col in df.select_dtypes(include=["object"]).columns:
        df[col] = df[col].map(lambda x: x.strip() if isinstance(x, str) else x)

    # 重置索引
    df = df.reset_index(drop=True)
    return df
