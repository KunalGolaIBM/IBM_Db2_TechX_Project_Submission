
import numpy as np
from sklearn.ensemble import IsolationForest

# Sample training data:
# [failed_login_count, connection_count, unusual_port_count]
TRAINING_DATA = np.array([
    [0, 10, 0],
    [1, 15, 0],
    [0, 20, 1],
    [2, 12, 0],
    [1, 18, 1],
    [0, 8, 0],
    [2, 25, 1],
    [1, 10, 0],
    [0, 16, 0],
    [1, 22, 1],
    [2, 14, 0],
    [0, 12, 1]
])

model = IsolationForest(
    n_estimators=100,
    contamination=0.15,
    random_state=42
)

model.fit(TRAINING_DATA)


def analyze_network_activity(
    failed_login_count,
    connection_count,
    unusual_port_count
):
    """Identify unusual activity using a trained ML model."""

    values = [
        failed_login_count,
        connection_count,
        unusual_port_count
    ]

    if any(not isinstance(value, (int, float)) for value in values):
        raise ValueError("All inputs must be numbers")

    if any(not np.isfinite(value) or value < 0 for value in values):
        raise ValueError("Inputs must be finite, non-negative numbers")

    sample = np.array([values])

    prediction = model.predict(sample)[0]
    anomaly_score = float(model.decision_function(sample)[0])

    return {
        "anomaly_detected": bool(prediction == -1),
        "anomaly_score": anomaly_score,
        "method": "Isolation Forest"
    }
