"""Leakage-safe preprocessing: every transformer is fitted on the training split only."""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler


@dataclass
class Split:
    X_train: np.ndarray
    X_test: np.ndarray
    y_train: np.ndarray
    y_test: np.ndarray
    feature_names: list
    classes: list
    config: dict = field(default_factory=dict)


def prepare(df: pd.DataFrame, target: str, k_features: int | None = None,
            test_size: float = 0.25, seed: int = 42, drop_duplicates: bool = True) -> Split:
    if target not in df.columns:
        raise ValueError(f"Target column '{target}' not found")
    data = df.drop_duplicates() if drop_duplicates else df.copy()
    data = data.dropna(subset=[target])
    y_raw = data[target]
    X = data.drop(columns=[target]).select_dtypes(include="number").replace([np.inf, -np.inf], np.nan)
    if X.shape[1] == 0:
        raise ValueError("No numeric feature columns available")
    le = LabelEncoder()
    y = le.fit_transform(y_raw.astype(str))
    if len(le.classes_) != 2:
        raise ValueError("This platform supports binary classification targets only")
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=test_size, random_state=seed, stratify=y)
    imputer = SimpleImputer(strategy="median").fit(X_tr)
    scaler = StandardScaler().fit(imputer.transform(X_tr))
    A_tr = scaler.transform(imputer.transform(X_tr))
    A_te = scaler.transform(imputer.transform(X_te))
    names = list(X.columns)
    if k_features and k_features < A_tr.shape[1]:
        sel = SelectKBest(f_classif, k=k_features).fit(A_tr, y_tr)
        A_tr, A_te = sel.transform(A_tr), sel.transform(A_te)
        names = [n for n, keep in zip(names, sel.get_support()) if keep]
    cfg = {"target": target, "test_size": test_size, "seed": seed, "k_features": k_features,
           "drop_duplicates": drop_duplicates, "imputer": "median", "scaler": "standard",
           "selected_features": names, "train_rows": int(len(y_tr)), "test_rows": int(len(y_te))}
    return Split(A_tr, A_te, y_tr, y_te, names, [str(c) for c in le.classes_], cfg)
