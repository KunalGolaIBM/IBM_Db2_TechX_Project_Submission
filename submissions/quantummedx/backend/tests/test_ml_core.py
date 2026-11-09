import numpy as np
import pandas as pd
import pytest
from sklearn.datasets import load_breast_cancer

from app.ml.analysis import analyze_dataframe
from app.ml.classical.models import run_classical
from app.ml.preprocessing import prepare
from app.ml.quantum.vqc import circuit_info, run_vqc


@pytest.fixture(scope="module")
def df():
    d = load_breast_cancer(as_frame=True).frame
    return d


def test_analysis_detects_issues():
    d = pd.DataFrame({"a": [1, 2, 2, np.nan, np.inf], "b": [1, 2, 2, 4, 5], "y": [0, 1, 1, 0, 1]})
    d = pd.concat([d, d.iloc[[1]]])
    r = analyze_dataframe(d, "y")
    assert r["missing_values"] == {"a": 1}
    assert r["duplicate_rows"] >= 1
    assert r["invalid_infinite_values"] == {"a": 1}
    assert r["class_distribution"] == {"1": 4, "0": 2}


def test_preprocessing_fits_on_train_only(df):
    s = prepare(df, "target", k_features=6, seed=7)
    assert s.X_train.shape[1] == 6 == len(s.feature_names)
    assert abs(s.X_train.mean()) < 1e-6          # scaler fitted on train
    assert abs(s.X_test.mean()) > 1e-6           # test not re-centred
    assert s.config["train_rows"] + s.config["test_rows"] == len(df)


@pytest.mark.parametrize("algo", ["logistic_regression", "random_forest", "svm"])
def test_classical_models(df, algo):
    s = prepare(df, "target", k_features=8)
    r = run_classical(s, algo)
    assert r["accuracy"] > 0.85 and 0 <= r["roc_auc"] <= 1
    assert sum(r["confusion"].values()) == s.config["test_rows"]


def test_rejects_non_binary_target(df):
    d = df.copy(); d["target"] = np.arange(len(d)) % 3
    with pytest.raises(ValueError):
        prepare(d, "target")


def test_vqc_runs_on_simulator(df):
    s = prepare(df, "target", k_features=4)
    info = circuit_info(4)
    assert info["qubits"] == 4 and info["num_parameters"] == 12
    r = run_vqc(s, n_qubits=4, maxiter=15, max_train=40)
    assert 0 <= r["accuracy"] <= 1
    assert "not real quantum hardware" in r["backend_info"]
    assert sum(r["confusion"].values()) == s.config["test_rows"]
