import pandas as pd
from typing import Dict, Any, Optional


def load_profile_from_excel(path: str = "data/shenakht_poosti.xlsx") -> Dict[str, Any]:
    # Reads the first sheet, first row as a dict
    df = pd.read_excel(path, engine="openpyxl")
    if df.empty:
        return {}
    row = df.iloc[0].to_dict()
    # Normalize NaN to empty string
    return {str(k).strip(): ("" if pd.isna(v) else v) for k, v in row.items()}
