"""Deterministic backend tools used by the agents. Every call is logged to Db2 (AGENT_ACTIVITIES).
Tools return aggregate summaries only: raw patient rows are never exposed to an LLM."""
import json
from typing import Callable

import pandas as pd
from sklearn.preprocessing import LabelEncoder

from app.ml.analysis import analyze_dataframe
from app.services import experiments as svc

AGENTS = {
    "data": "Data Intelligence Agent",
    "clinical": "Clinical Data Analysis Agent",
    "classical": "Classical ML Agent",
    "quantum": "Quantum ML Agent",
    "research": "Research & Verification Agent",
}


class Toolbox:
    def __init__(self, repo, dataset: dict, target: str, run_id: int, quantum_qubits: int = 4, quantum_iter: int = 20):
        self.repo, self.dataset, self.target, self.run_id = repo, dataset, target, run_id
        self.qubits, self.iters = quantum_qubits, quantum_iter
        self.out: dict = {}  # last output per tool, used to assemble the report

    def _logged(self, agent_key: str, tool: str, fn: Callable[[], dict], input_ref: str = "") -> dict:
        agent = AGENTS[agent_key]
        try:
            out = fn()
        except Exception as exc:
            self.repo.log_activity(self.run_id, agent, tool, "FAILED", input_ref, "", str(exc))
            raise
        self.repo.log_activity(self.run_id, agent, tool, "COMPLETED", input_ref, json.dumps(out, default=str)[:19000])
        self.out[tool.split(":")[0]] = out
        return out

    def _df(self) -> pd.DataFrame:
        return pd.read_csv(self.dataset["storage_ref"])

    # Agent 1
    def data_quality(self) -> dict:
        def fn():
            a = analyze_dataframe(self._df(), self.target)
            return {k: a[k] for k in ("rows", "columns", "missing_total", "missing_values", "duplicate_rows",
                                      "invalid_infinite_values", "class_distribution")}
        return self._logged("data", "data_quality", fn, f"dataset:{self.dataset['dataset_id']}")

    # Agent 2
    def feature_patterns(self, top_n: int = 5) -> dict:
        def fn():
            df = self._df()
            y = LabelEncoder().fit_transform(df[self.target].astype(str))
            num = df.drop(columns=[self.target]).select_dtypes(include="number")
            corr = num.apply(lambda c: c.fillna(c.median()).corr(pd.Series(y, index=c.index))).abs().sort_values(ascending=False)
            return {"top_features_by_abs_correlation_with_target": {k: round(float(v), 3) for k, v in corr.head(top_n).items()},
                    "note": "Correlation is descriptive and not evidence of causation."}
        return self._logged("clinical", "feature_patterns", fn, f"dataset:{self.dataset['dataset_id']}")

    # Agent 3
    def run_classical(self, algorithm: str) -> dict:
        def fn():
            exp_id = svc.run_classical_experiment(self.repo, self.dataset, self.target, algorithm)
            return {"experiment_id": exp_id, "algorithm": algorithm}
        return self._logged("classical", f"run_classical:{algorithm}", fn, f"dataset:{self.dataset['dataset_id']}")

    # Agent 4 (runs synchronously inside the agent run)
    def run_quantum(self) -> dict:
        def fn():
            exp_id, job = svc.start_quantum_experiment(self.repo, self.dataset, self.target, self.qubits, self.iters, 0.25, 42)
            job()
            exp = self.repo.get_experiment(exp_id)
            if exp["status"] != "COMPLETED":
                raise RuntimeError(exp.get("error_message") or "quantum experiment failed")
            return {"experiment_id": exp_id, "algorithm": "vqc", "backend": "local simulator"}
        return self._logged("quantum", "run_quantum_vqc", fn, f"dataset:{self.dataset['dataset_id']}")

    # Agent 5
    def stored_results(self) -> dict:
        def fn():
            rows = self.repo.comparison(self.dataset["dataset_id"])
            return {"results": [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items() if k != "created_at"} for r in rows]}
        return self._logged("research", "fetch_results_from_db", fn, f"dataset:{self.dataset['dataset_id']}")
