from __future__ import annotations

import pandas as pd


def find_duplicates(dataframe: pd.DataFrame, key_column: str) -> pd.DataFrame:
    if dataframe.empty or key_column not in dataframe.columns:
        return pd.DataFrame(columns=dataframe.columns)
    mask = dataframe[key_column].fillna("").astype(str).str.strip().duplicated(keep=False)
    duplicates = dataframe.loc[mask].copy()
    if duplicates.empty:
        return pd.DataFrame(columns=dataframe.columns)
    return duplicates.sort_values(by=key_column, kind="stable").reset_index(drop=True)
