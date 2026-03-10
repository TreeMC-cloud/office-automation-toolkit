from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pandas as pd


def _extension(source: Any) -> str:
    return Path(getattr(source, "name", str(source))).suffix.lower()


def _read_bytes(source: Any) -> bytes:
    if hasattr(source, "getvalue"):
        return source.getvalue()
    if isinstance(source, (str, Path)):
        return Path(source).read_bytes()
    raise ValueError("不支持的输入源")


def _read_single(source: Any) -> pd.DataFrame:
    suffix = _extension(source)
    raw = _read_bytes(source)
    if suffix == ".csv":
        for encoding in ["utf-8-sig", "utf-8", "gbk", "gb18030"]:
            try:
                return pd.read_csv(io.BytesIO(raw), encoding=encoding)
            except Exception:
                continue
        raise ValueError(f"CSV 读取失败：{getattr(source, 'name', source)}")
    if suffix in {".xlsx", ".xls"}:
        xls = pd.ExcelFile(io.BytesIO(raw))
        frames = []
        for sheet in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet)
            df["__sheet_name"] = sheet
            frames.append(df)
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    raise ValueError(f"不支持的文件类型：{suffix}")


def load_uploaded_files(files: list[Any]) -> pd.DataFrame:
    frames = []
    for file in files:
        frame = _read_single(file)
        frame["__source_file"] = getattr(file, "name", str(file))
        frames.append(frame)
    if not frames:
        return pd.DataFrame()
    merged = pd.concat(frames, ignore_index=True)
    merged.columns = [str(column).strip() for column in merged.columns]

    # 列名一致性检查：超过 30% NaN 的列发出警告
    for col in merged.columns:
        na_rate = merged[col].isna().sum() / len(merged)
        if na_rate > 0.3:
            print(f"[file_ingestion] 警告：列 '{col}' 有 {na_rate:.0%} 的值为空，可能是多文件列名不一致导致。")

    return merged
