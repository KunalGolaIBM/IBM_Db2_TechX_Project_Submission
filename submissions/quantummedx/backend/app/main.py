import io
import json
import os
import re
import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.core.config import ConfigError
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.ml.analysis import analyze_dataframe
from app.ml.classical.models import ALGORITHMS
from app.services import experiments as svc

app = FastAPI(title="QuantumMedX API", version="0.1.0",
              description="Research/education prototype. Not a clinically validated diagnostic tool.")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
                   allow_methods=["GET", "POST", "DELETE"], allow_headers=["Authorization", "Content-Type"])

STORAGE = Path(os.getenv("STORAGE_DIR", "storage")).resolve()
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
_failed_logins: dict = defaultdict(list)
_repo = None


def get_repo():
    """Lazily connect to Db2. If Db2 is not configured or reachable, say so honestly (HTTP 503)."""
    global _repo
    if _repo is None:
        try:
            from app.database.db2 import Db2Pool
            from app.repositories.db2_repo import Repo
            pool = Db2Pool()
            pool.health_check()
            _repo = Repo(pool)
        except ConfigError as exc:
            raise HTTPException(503, f"Db2 setup required: {exc}")
        except Exception:
            raise HTTPException(503, "IBM Db2 is not reachable. Check that the container is running and .env is correct.")
    return _repo


def current_user(authorization: Optional[str] = Header(None), repo=Depends(get_repo)) -> dict:
    token = authorization.split(" ", 1)[1] if authorization and authorization.lower().startswith("bearer ") else None
    claims = decode_token(token) if token else None
    user = repo.user_by_id(claims["sub"]) if claims else None
    if not user or not user["is_active"]:
        raise HTTPException(401, "Not authenticated")
    return user


def owned_dataset(dataset_id: int, user: dict, repo) -> dict:
    ds = repo.get_dataset(dataset_id)
    if not ds or (ds["owner_id"] != user["user_id"] and user["role"] != "ADMIN"):
        raise HTTPException(404, "Dataset not found")  # same answer for missing and not-yours
    return ds


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=128)


class Registration(Credentials):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=255)


class ClassicalRequest(BaseModel):
    dataset_id: int
    algorithm: str = "logistic_regression"
    target_column: Optional[str] = None
    k_features: int = Field(8, ge=2, le=100)
    test_size: float = Field(0.25, gt=0.05, lt=0.5)
    seed: int = 42


class QuantumRequest(BaseModel):
    dataset_id: int
    target_column: Optional[str] = None
    n_qubits: int = Field(4, ge=2, le=6)
    maxiter: int = Field(30, ge=5, le=200)
    test_size: float = Field(0.25, gt=0.05, lt=0.5)
    seed: int = 42


# ---- system
@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/system/db-status")
def db_status(repo=Depends(get_repo)):
    return repo.pool.health_check()


# ---- auth
@app.post("/api/auth/register", status_code=201)
def register(body: Registration, repo=Depends(get_repo)):
    if repo.user_by_username(body.username):
        raise HTTPException(409, "Username already taken")
    uid = repo.create_user(body.username, body.email, hash_password(body.password))
    return {"user_id": uid, "username": body.username}


@app.post("/api/auth/login")
def login(body: Credentials, repo=Depends(get_repo)):
    now = time.time()
    _failed_logins[body.username] = [t for t in _failed_logins[body.username] if now - t < 300]
    if len(_failed_logins[body.username]) >= 5:
        raise HTTPException(429, "Too many failed attempts. Try again in a few minutes.")
    user = repo.user_by_username(body.username)
    if not user or not user["is_active"] or not verify_password(body.password, user["password_hash"]):
        _failed_logins[body.username].append(now)
        raise HTTPException(401, "Invalid credentials")
    repo.audit(user["user_id"], "LOGIN", "")
    return {"access_token": create_token(user["user_id"], user["role"]), "token_type": "bearer"}


@app.get("/api/auth/me")
def me(user=Depends(current_user)):
    return {k: user[k] for k in ("user_id", "username", "email", "role")}


# ---- datasets
@app.post("/api/datasets/upload", status_code=201)
async def upload_dataset(file: UploadFile = File(...), target_column: Optional[str] = Form(None),
                         source: str = Form("user upload"), user=Depends(current_user), repo=Depends(get_repo)):
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(400, "Only .csv files are accepted")
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File exceeds the 10 MB limit")
    try:
        df = pd.read_csv(io.BytesIO(raw))
        analysis = analyze_dataframe(df, target_column)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception:
        raise HTTPException(400, "File could not be parsed as CSV")
    STORAGE.mkdir(parents=True, exist_ok=True)
    path = STORAGE / f"{uuid.uuid4().hex}.csv"
    path.write_bytes(raw)
    name = re.sub(r"[^A-Za-z0-9_. -]", "_", Path(file.filename).name)[:200]
    did = repo.create_dataset(user["user_id"], name, source[:250], str(path), target_column, analysis)
    return {"dataset_id": did, "analysis": analysis}


@app.get("/api/datasets")
def list_datasets(limit: int = 50, offset: int = 0, user=Depends(current_user), repo=Depends(get_repo)):
    owner = None if user["role"] == "ADMIN" else user["user_id"]
    return repo.list_datasets(owner, min(max(limit, 1), 200), max(offset, 0))


@app.get("/api/datasets/{dataset_id}/analysis")
def dataset_analysis(dataset_id: int, user=Depends(current_user), repo=Depends(get_repo)):
    ds = owned_dataset(dataset_id, user, repo)
    return analyze_dataframe(pd.read_csv(ds["storage_ref"]), ds["target_column"])


@app.get("/api/datasets/{dataset_id}/preview")
def dataset_preview(dataset_id: int, rows: int = 10, user=Depends(current_user), repo=Depends(get_repo)):
    ds = owned_dataset(dataset_id, user, repo)
    head = pd.read_csv(ds["storage_ref"], nrows=min(max(rows, 1), 50))
    return json.loads(head.to_json(orient="records"))


@app.delete("/api/datasets/{dataset_id}", status_code=204)
def delete_dataset(dataset_id: int, user=Depends(current_user), repo=Depends(get_repo)):
    ds = owned_dataset(dataset_id, user, repo)
    repo.delete_dataset(dataset_id, user["user_id"])
    p = Path(ds["storage_ref"]).resolve()
    if STORAGE in p.parents and p.is_file():  # path-traversal guard
        p.unlink()


# ---- models
def _target(req, ds) -> str:
    target = req.target_column or ds["target_column"]
    if not target:
        raise HTTPException(400, "target_column is required (none stored for this dataset)")
    return target


@app.post("/api/models/classical/train", status_code=201)
def train_classical(req: ClassicalRequest, user=Depends(current_user), repo=Depends(get_repo)):
    if req.algorithm not in ALGORITHMS:
        raise HTTPException(400, f"algorithm must be one of {sorted(ALGORITHMS)}")
    ds = owned_dataset(req.dataset_id, user, repo)
    try:
        exp_id = svc.run_classical_experiment(repo, ds, _target(req, ds), req.algorithm, req.k_features, req.test_size, req.seed)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return repo.get_experiment(exp_id)


@app.post("/api/models/quantum/train", status_code=202)
def train_quantum(req: QuantumRequest, background: BackgroundTasks, user=Depends(current_user), repo=Depends(get_repo)):
    ds = owned_dataset(req.dataset_id, user, repo)
    try:
        exp_id, job = svc.start_quantum_experiment(repo, ds, _target(req, ds), req.n_qubits, req.maxiter, req.test_size, req.seed)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    background.add_task(job)
    return {"experiment_id": exp_id, "status": "RUNNING", "poll": f"/api/models/results/{exp_id}"}


@app.get("/api/models/results/{experiment_id}")
def model_result(experiment_id: int, user=Depends(current_user), repo=Depends(get_repo)):
    exp = repo.get_experiment(experiment_id)
    if not exp:
        raise HTTPException(404, "Experiment not found")
    owned_dataset(exp["dataset_id"], user, repo)
    for k in ("confusion_json", "extra_json"):
        if exp.get(k):
            exp[k.replace("_json", "")] = json.loads(exp.pop(k))
    return exp


@app.get("/api/dashboard/model-comparison")
def model_comparison(dataset_id: int, user=Depends(current_user), repo=Depends(get_repo)):
    owned_dataset(dataset_id, user, repo)
    return {"dataset_id": dataset_id, "results": repo.comparison(dataset_id),
            "note": "Metrics come from stored experiments only. Small simulator runs do not demonstrate quantum advantage."}


# ---- agents and reports
class AgentRunRequest(BaseModel):
    dataset_id: int
    target_column: Optional[str] = None
    mode: str = Field("CREWAI", pattern="^(CREWAI|DETERMINISTIC)$")


def _owned_run(run_id: int, user: dict, repo) -> dict:
    run = repo.get_run(run_id)
    if not run or (run["owner_id"] != user["user_id"] and user["role"] != "ADMIN"):
        raise HTTPException(404, "Run not found")
    return run


@app.post("/api/agents/run", status_code=202)
def start_agent_run(req: AgentRunRequest, background: BackgroundTasks, user=Depends(current_user), repo=Depends(get_repo)):
    from app.agents.pipeline import run_pipeline
    ds = owned_dataset(req.dataset_id, user, repo)
    target = _target(req, ds)
    if req.mode == "CREWAI" and not all(os.getenv(k) for k in ("LLM_PROVIDER", "LLM_MODEL", "LLM_API_KEY")):
        raise HTTPException(400, "CrewAI mode needs LLM_PROVIDER, LLM_MODEL and LLM_API_KEY configured on the server. "
                                 "Use mode DETERMINISTIC to run the same tool pipeline without an LLM.")
    run_id = repo.create_agent_run(ds["dataset_id"], user["user_id"], req.mode)

    def job():
        try:
            run_pipeline(repo, ds, target, user["user_id"], req.mode, run_id)
        except Exception:
            pass  # failure is already recorded on the run in Db2

    background.add_task(job)
    return {"run_id": run_id, "status": "RUNNING", "mode": req.mode}


@app.get("/api/agents/runs")
def list_agent_runs(user=Depends(current_user), repo=Depends(get_repo)):
    return repo.list_runs(None if user["role"] == "ADMIN" else user["user_id"])


@app.get("/api/agents/runs/{run_id}")
def get_agent_run(run_id: int, user=Depends(current_user), repo=Depends(get_repo)):
    run = _owned_run(run_id, user, repo)
    run.pop("owner_id", None)
    return run


@app.get("/api/agents/activity/{run_id}")
def agent_activity(run_id: int, user=Depends(current_user), repo=Depends(get_repo)):
    _owned_run(run_id, user, repo)
    return repo.activities(run_id)


@app.get("/api/reports")
def list_reports(user=Depends(current_user), repo=Depends(get_repo)):
    return repo.list_reports(None if user["role"] == "ADMIN" else user["user_id"])


@app.get("/api/reports/{report_id}")
def get_report(report_id: int, user=Depends(current_user), repo=Depends(get_repo)):
    rep = repo.get_report(report_id)
    if not rep or (rep["owner_id"] != user["user_id"] and user["role"] != "ADMIN"):
        raise HTTPException(404, "Report not found")
    rep.pop("owner_id", None)
    return rep
