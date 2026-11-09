"""API logic tests using an in-memory stand-in for the Db2 repository.
These prove routing, auth, validation and ownership rules. They do NOT prove Db2 behaviour;
see test_db2_integration.py for that."""
import io
import itertools
import json

import pytest
from fastapi.testclient import TestClient
from sklearn.datasets import load_breast_cancer

from app import main


class FakePool:
    def health_check(self):
        return {"connected": True, "server": "fake", "database": "fake"}


class FakeRepo:
    def __init__(self):
        self.pool = FakePool()
        self.users, self.datasets, self.configs, self.exps, self.results = {}, {}, {}, {}, {}
        self._ids = itertools.count(1)

    def create_user(self, username, email, pw_hash, role="RESEARCHER"):
        uid = next(self._ids)
        self.users[uid] = dict(user_id=uid, username=username, email=email, password_hash=pw_hash, role=role, is_active=1)
        return uid

    def user_by_username(self, u): return next((x for x in self.users.values() if x["username"] == u), None)
    def user_by_id(self, i): return self.users.get(i)
    def audit(self, *a): pass

    def create_dataset(self, owner_id, name, source, storage_ref, target, analysis):
        did = next(self._ids)
        self.datasets[did] = dict(dataset_id=did, owner_id=owner_id, name=name, storage_ref=storage_ref, target_column=target, status="ANALYZED",
                                  row_count=analysis["rows"], column_count=analysis["columns"])
        return did

    def list_datasets(self, owner, limit, offset):
        return [d for d in self.datasets.values() if owner is None or d["owner_id"] == owner]

    def get_dataset(self, i): return self.datasets.get(i)
    def delete_dataset(self, i, uid): self.datasets.pop(i, None)
    def save_preprocessing(self, did, cfg):
        i = next(self._ids); self.configs[i] = cfg; return i

    def create_experiment(self, did, cfg, family, algo, params):
        i = next(self._ids)
        self.exps[i] = dict(experiment_id=i, dataset_id=did, model_family=family, algorithm=algo, status="RUNNING", error_message=None)
        return i

    def finish_experiment(self, i, result, error=None):
        if result is None:
            self.exps[i].update(status="FAILED", error_message=error); return
        self.results[i] = result
        self.exps[i]["status"] = "COMPLETED"

    def get_experiment(self, i):
        e = self.exps.get(i)
        if not e: return None
        r = self.results.get(i)
        out = dict(e)
        if r:
            out.update(accuracy=r["accuracy"], f1_score=r["f1"], confusion_json=json.dumps(r["confusion"]),
                       backend_info=r["backend_info"], extra_json=json.dumps({"quantum": r.get("quantum")}))
        return out

    def comparison(self, did):
        return [dict(experiment_id=i, model_family=e["model_family"], algorithm=e["algorithm"], accuracy=self.results[i]["accuracy"])
                for i, e in self.exps.items() if e["dataset_id"] == did and e["status"] == "COMPLETED"]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret-which-is-long-enough")
    monkeypatch.setattr(main, "STORAGE", tmp_path)
    main._failed_logins.clear()
    repo = FakeRepo()
    main.app.dependency_overrides[main.get_repo] = lambda: repo
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def csv_bytes():
    return load_breast_cancer(as_frame=True).frame.to_csv(index=False).encode()


def signup(c, name):
    assert c.post("/api/auth/register", json={"username": name, "password": "correct-horse-1", "email": f"{name}@example.com"}).status_code == 201
    tok = c.post("/api/auth/login", json={"username": name, "password": "correct-horse-1"}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def upload(c, h, name="bc.csv", data=None, target="target"):
    return c.post("/api/datasets/upload", headers=h, files={"file": (name, data or csv_bytes(), "text/csv")}, data={"target_column": target})


def test_health_and_unconfigured_db_is_honest(monkeypatch):
    c = TestClient(main.app)
    assert c.get("/health").json() == {"status": "ok"}
    monkeypatch.delenv("DB2_PASSWORD", raising=False)
    monkeypatch.setattr(main, "_repo", None)
    r = c.get("/api/system/db-status")
    assert r.status_code == 503 and "Db2 setup required" in r.json()["detail"]


def test_auth_flow_and_protection(client):
    assert client.get("/api/datasets").status_code == 401
    h = signup(client, "alice")
    assert client.get("/api/auth/me", headers=h).json()["username"] == "alice"
    assert client.post("/api/auth/login", json={"username": "alice", "password": "wrong-password"}).status_code == 401
    assert client.post("/api/auth/register", json={"username": "alice", "password": "correct-horse-1", "email": "a@b.co"}).status_code == 409


def test_login_rate_limit(client):
    signup(client, "bob")
    codes = [client.post("/api/auth/login", json={"username": "bob", "password": "nope-nope-1"}).status_code for _ in range(6)]
    assert codes[:5] == [401] * 5 and codes[5] == 429


def test_upload_validation(client):
    h = signup(client, "carol")
    assert upload(client, h, name="x.exe").status_code == 400
    assert upload(client, h, data=b"\x00\x01notcsv", name="x.csv").status_code == 400
    assert upload(client, h, target="missing_col").status_code == 400
    assert upload(client, h).status_code == 201


def test_user_isolation(client):
    ha, hb = signup(client, "dave"), signup(client, "erin")
    did = upload(client, ha).json()["dataset_id"]
    assert client.get(f"/api/datasets/{did}/analysis", headers=hb).status_code == 404
    assert client.delete(f"/api/datasets/{did}", headers=hb).status_code == 404
    assert client.post("/api/models/classical/train", headers=hb, json={"dataset_id": did}).status_code == 404
    assert client.get("/api/datasets", headers=hb).json() == []


def test_classical_train_and_compare(client):
    h = signup(client, "frank")
    did = upload(client, h).json()["dataset_id"]
    r = client.post("/api/models/classical/train", headers=h, json={"dataset_id": did, "algorithm": "random_forest"})
    assert r.status_code == 201 and r.json()["accuracy"] > 0.85
    assert client.post("/api/models/classical/train", headers=h, json={"dataset_id": did, "algorithm": "bogus"}).status_code == 400
    comp = client.get(f"/api/dashboard/model-comparison?dataset_id={did}", headers=h).json()
    assert len(comp["results"]) == 1 and "quantum advantage" in comp["note"]


def test_quantum_train_background(client):
    h = signup(client, "gina")
    did = upload(client, h).json()["dataset_id"]
    r = client.post("/api/models/quantum/train", headers=h, json={"dataset_id": did, "n_qubits": 4, "maxiter": 5})
    assert r.status_code == 202
    res = client.get(r.json()["poll"], headers=h).json()
    assert res["status"] == "COMPLETED" and "not real quantum hardware" in res["backend_info"]
    assert client.post("/api/models/quantum/train", headers=h, json={"dataset_id": did, "n_qubits": 9}).status_code == 422
