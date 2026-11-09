"""Deterministic dataset quality analysis (no LLM involved)."""
import numpy as np
import pandas as pd


def analyze_dataframe(df: pd.DataFrame, target: str | None = None) -> dict:
    numeric = df.select_dtypes(include="number")
    inf_counts = {c: int(np.isinf(numeric[c]).sum()) for c in numeric.columns if np.isinf(numeric[c]).any()}
    missing = {c: int(n) for c, n in df.isna().sum().items() if n > 0}
    out = {
        "rows": int(len(df)),
        "columns": int(df.shape[1]),
        "schema": {c: str(t) for c, t in df.dtypes.items()},
        "numeric_columns": list(numeric.columns),
        "categorical_columns": [c for c in df.columns if c not in numeric.columns],
        "missing_values": missing,
        "missing_total": int(sum(missing.values())),
        "duplicate_rows": int(df.duplicated().sum()),
        "invalid_infinite_values": inf_counts,
        "stats": json_safe(numeric.describe().round(4).to_dict()),
    }
    if target is not None:
        if target not in df.columns:
            raise ValueError(f"Target column '{target}' not found")
        out["target"] = target
        out["class_distribution"] = {str(k): int(v) for k, v in df[target].value_counts().items()}
    return out


def json_safe(obj):
    if isinstance(obj, dict):
        return {str(k): json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (np.floating, float)):
        return None if np.isnan(obj) else float(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    return obj
