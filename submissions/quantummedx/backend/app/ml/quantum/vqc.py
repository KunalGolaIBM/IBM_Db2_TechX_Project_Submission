"""Variational Quantum Classifier run on a local Qiskit simulator (never real hardware)."""
import time

import numpy as np
from qiskit.circuit.library import RealAmplitudes, ZZFeatureMap
from qiskit.primitives import StatevectorSampler
from qiskit_machine_learning.algorithms import VQC
from qiskit_machine_learning.optimizers import COBYLA
from sklearn.preprocessing import MinMaxScaler

from app.ml.metrics import evaluate

MAX_QUBITS = 6  # keeps simulator runtime practical


def build_circuit(n_qubits: int, reps: int = 1, ansatz_reps: int = 2):
    fmap = ZZFeatureMap(feature_dimension=n_qubits, reps=reps, entanglement="linear")
    ansatz = RealAmplitudes(num_qubits=n_qubits, reps=ansatz_reps, entanglement="linear")
    return fmap, ansatz, fmap.compose(ansatz)


def circuit_info(n_qubits: int, reps: int = 1, ansatz_reps: int = 2) -> dict:
    fmap, ansatz, full = build_circuit(n_qubits, reps, ansatz_reps)
    return {"qubits": n_qubits, "feature_map": "ZZFeatureMap(linear entanglement)",
            "ansatz": "RealAmplitudes(linear entanglement)", "num_parameters": ansatz.num_parameters,
            "depth": int(full.decompose().depth()), "diagram": str(full.decompose(reps=1).draw("text", fold=120))}


def run_vqc(split, n_qubits: int = 4, maxiter: int = 40, max_train: int = 120,
            seed: int = 42, reps: int = 1, ansatz_reps: int = 2) -> dict:
    if not 2 <= n_qubits <= MAX_QUBITS:
        raise ValueError(f"n_qubits must be between 2 and {MAX_QUBITS}")
    if split.X_train.shape[1] < n_qubits:
        raise ValueError("Not enough selected features for the requested qubit count")
    X_tr, X_te = split.X_train[:, :n_qubits], split.X_test[:, :n_qubits]
    scaler = MinMaxScaler(feature_range=(0, np.pi)).fit(X_tr)
    X_tr, X_te = scaler.transform(X_tr), np.clip(scaler.transform(X_te), 0, np.pi)
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(X_tr))[:max_train]
    X_tr, y_tr = X_tr[idx], split.y_train[idx]
    fmap, ansatz, _ = build_circuit(n_qubits, reps, ansatz_reps)
    rng_state = np.random.seed(seed)  # noqa: F841 (VQC initial point uses numpy global RNG)
    clf = VQC(feature_map=fmap, ansatz=ansatz, optimizer=COBYLA(maxiter=maxiter),
              sampler=StatevectorSampler(seed=seed), initial_point=rng.random(ansatz.num_parameters))
    t0 = time.perf_counter()
    clf.fit(X_tr, np.eye(2)[y_tr])
    train_s = time.perf_counter() - t0
    t1 = time.perf_counter()
    pred = clf.predict(X_te)
    pred = np.argmax(pred, axis=1) if pred.ndim == 2 else pred
    infer_s = time.perf_counter() - t1
    res = evaluate(split.y_test, pred)  # hard labels only; ROC-AUC not computed for VQC here
    res.update(train_seconds=round(train_s, 4), infer_seconds=round(infer_s, 4), algorithm="vqc",
               backend_info="qiskit StatevectorSampler (local simulator, not real quantum hardware)",
               quantum={**circuit_info(n_qubits, reps, ansatz_reps), "optimizer": f"COBYLA(maxiter={maxiter})",
                        "train_samples_used": int(len(y_tr)), "features_used": split.feature_names[:n_qubits]})
    return res
