"""Orchestrates preprocessing + model runs and persists everything through the repository."""
import pandas as pd

from app.ml.classical.models import run_classical
from app.ml.preprocessing import prepare
from app.ml.quantum.vqc import run_vqc


def _split(repo, dataset: dict, target: str, k_features: int, test_size: float, seed: int):
    df = pd.read_csv(dataset["storage_ref"])
    split = prepare(df, target, k_features=k_features, test_size=test_size, seed=seed)
    return split, repo.save_preprocessing(dataset["dataset_id"], split.config)


def run_classical_experiment(repo, dataset: dict, target: str, algorithm: str,
                             k_features: int = 8, test_size: float = 0.25, seed: int = 42) -> int:
    split, cfg_id = _split(repo, dataset, target, k_features, test_size, seed)
    exp_id = repo.create_experiment(dataset["dataset_id"], cfg_id, "CLASSICAL", algorithm, {"k_features": k_features, "seed": seed})
    try:
        repo.finish_experiment(exp_id, run_classical(split, algorithm, seed))
    except Exception as exc:
        repo.finish_experiment(exp_id, None, str(exc))
        raise
    return exp_id


def start_quantum_experiment(repo, dataset: dict, target: str, n_qubits: int, maxiter: int,
                             test_size: float, seed: int):
    """Validate + persist the experiment row now; return (experiment_id, job) so the caller can run the job in the background."""
    split, cfg_id = _split(repo, dataset, target, max(n_qubits, 4), test_size, seed)
    exp_id = repo.create_experiment(dataset["dataset_id"], cfg_id, "QUANTUM", "vqc",
                                    {"n_qubits": n_qubits, "maxiter": maxiter, "seed": seed})

    def job():
        try:
            repo.finish_experiment(exp_id, run_vqc(split, n_qubits=n_qubits, maxiter=maxiter, seed=seed))
        except Exception as exc:
            repo.finish_experiment(exp_id, None, str(exc))

    return exp_id, job
