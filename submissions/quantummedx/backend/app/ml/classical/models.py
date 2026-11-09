import time

from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC

from app.ml.metrics import evaluate

ALGORITHMS = {
    "logistic_regression": lambda seed: LogisticRegression(max_iter=1000, random_state=seed),
    "random_forest": lambda seed: RandomForestClassifier(n_estimators=200, random_state=seed),
    "svm": lambda seed: SVC(probability=True, random_state=seed),
}


def run_classical(split, algorithm: str, seed: int = 42) -> dict:
    if algorithm not in ALGORITHMS:
        raise ValueError(f"Unknown algorithm '{algorithm}'. Choose from {sorted(ALGORITHMS)}")
    model = ALGORITHMS[algorithm](seed)
    t0 = time.perf_counter()
    model.fit(split.X_train, split.y_train)
    train_s = time.perf_counter() - t0
    t1 = time.perf_counter()
    pred = model.predict(split.X_test)
    score = model.predict_proba(split.X_test)[:, 1]
    infer_s = time.perf_counter() - t1
    res = evaluate(split.y_test, pred, score)
    res.update(train_seconds=round(train_s, 4), infer_seconds=round(infer_s, 4),
               algorithm=algorithm, backend_info="scikit-learn (CPU)")
    return res
