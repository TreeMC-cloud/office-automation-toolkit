from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pandas as pd


SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


def _detect_extension(source: Any) -> str:
    name = getattr(source, "name", str(source))
    suffix = Path(name).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"暂不支持的文件类型：{suffix}")
    return suffix


def _read_bytes(source: Any) -> bytes:
    if hasattr(source, "getvalue"):
        return source.getvalue()
    if isinstance(source, (str, Path)):
        return Path(source).read_bytes()
    if hasattr(source, "read"):
        position = source.tell() if hasattr(source, "tell") else None
        data = source.read()
        if position is not None and hasattr(source, "seek"):
            source.seek(position)
        return data if isinstance(data, bytes) else str(data).encode("utf-8")
    raise ValueError("无法读取输入文件")


def _clean_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    result = dataframe.copy()
    result.columns = [str(column).strip() for column in result.columns]
    result = result.dropna(how="all")
    result = result.dropna(axis=1, how="all")
    for column in result.columns:
        if result[column].dtype == object:
            result[column] = result[column].fillna("").astype(str).str.strip()
    return result.reset_index(drop=True)


def list_sheets(source: Any) -> list[str]:
    extension = _detect_extension(source)
    if extension == ".csv":
        return ["CSV"]
    excel = pd.ExcelFile(io.BytesIO(_read_bytes(source)))
    return excel.sheet_names


def read_dataframe(source: Any, sheet_name: str | None = None) -> pd.DataFrame:
    extension = _detect_extension(source)
    raw_bytes = _read_bytes(source)
    if extension == ".csv":
        encodings = ["utf-8-sig", "utf-8", "gbk", "gb18030"]
        last_error: Exception | None = None
        for encoding in encodings:
            try:
                dataframe = pd.read_csv(io.BytesIO(raw_bytes), encoding=encoding)
                return _clean_dataframe(dataframe)
            except Exception as exc:  # pragma: no cover - 兼容不同编码
                last_error = exc
        raise ValueError(f"CSV 读取失败：{last_error}")
    dataframe = pd.read_excel(io.BytesIO(raw_bytes), sheet_name=sheet_name or 0)
    return _clean_dataframe(dataframe)
