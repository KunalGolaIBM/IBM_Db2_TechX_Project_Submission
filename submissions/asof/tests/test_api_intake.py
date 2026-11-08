"""Policy intake over HTTP: the upload is checked before anything is parsed, only an editor can upload or decide,
and on Db2 a draft goes from PDF to preview to clause versions in force."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from pdfs import REVISION, make_pdf
from test_api import FakeAssistant, FakeGate
from test_intake import CREDITS, clause, num

from asof import intake, schema, seed
from asof.api import create_app
from asof.config import Settings
from asof.llm import LLMResult
from asof.schemas import IntakeResult

PDF = make_pdf([REVISION])
UPLOAD = "/api/policy/drafts?doc_id=AURELIA-CSP&name=revision.pdf"
CREDIT_TEXT = ("Travel credits are valid for 24 months from the date they are issued. The booking must be made before the "
               "credit expires, but the flight itself may take place after the expiry date.")


class ScriptedIntake:
    info = "scripted:intake"

    def __init__(self, result: IntakeResult):
        self.result, self.calls = result, 0

    def structured(self, schema, messages, choices=None, max_chars=None):
        self.calls += 1
        return LLMResult(self.result, 3, None, None, 1)


def proposals() -> IntakeResult:
    return IntakeResult(clauses=[
        clause(), clause(text=CREDIT_TEXT, cid="CRD-001", area="travel_credit", start="2027-03-01", quote=CREDITS,
                         rule=[num("credit_validity_months", 24)], title="Travel credit validity")])


def local(settings=None, model=None, schema_name="ASOF") -> TestClient:
    app = create_app(settings or Settings(_env_file=None), gate=FakeGate(), assistant=FakeAssistant(),
                     intake_model=model or ScriptedIntake(proposals()), schema=schema_name)
    return TestClient(app, client=("127.0.0.1", 50000))


def pdf_post(c, body=PDF, path=UPLOAD, content_type="application/pdf", **headers):
    return c.post(path, content=body, headers={"content-type": content_type, **headers})


def test_the_upload_must_be_a_pdf_body():
    model = ScriptedIntake(proposals())
    c = local(model=model)
    assert pdf_post(c, content_type="application/json").status_code == 415
    r = pdf_post(c, body=b"not a pdf at all")
    assert r.status_code == 422 and "not a PDF" in r.json()["detail"]
    assert pdf_post(c, path="/api/policy/drafts?doc_id=OTHER-AIRLINE").status_code == 422
    assert model.calls == 0  # nothing reached the model


def test_the_upload_limit_is_two_megabytes_on_that_route_only():
    c = local()
    big = b"%PDF-1.4\n" + b"0" * (intake.MAX_PDF_BYTES + 10)
    assert pdf_post(c, body=big).status_code == 413
    assert c.post("/api/gate", content=b"{" + b" " * 70_000 + b"}",
                  headers={"content-type": "application/json"}).status_code == 413  # still 64 KB elsewhere


def test_only_an_editor_may_upload_or_decide():
    remote = TestClient(create_app(Settings(_env_file=None), gate=FakeGate(), assistant=FakeAssistant(),
                                   intake_model=ScriptedIntake(proposals())), client=("203.0.113.7", 50000))
    assert pdf_post(remote).status_code == 403
    assert remote.post("/api/policy/drafts/1/decision", json={"approve": False}).status_code == 403
    token = local(Settings(_env_file=None, asof_editor_token="s3cret-editor-token"))
    assert pdf_post(token).status_code == 403
    assert token.post("/api/policy/drafts/1/decision", json={"approve": False},
                      headers={"X-AsOf-Editor-Token": "wrong"}).status_code == 403


@pytest.mark.parametrize("body", [
    {"approve": True, "accept": [0]}, {"approve": True, "accept": [13]}, {"approve": True, "accept": list(range(1, 14))},
    {"approve": "yes please"}, {"approve": True, "accept": [1], "sneaky": 1},
])
def test_decisions_are_validated_before_db2(body):
    assert local().post("/api/policy/drafts/1/decision", json=body).status_code == 422


def test_a_preview_must_be_an_approval():
    r = local().post("/api/policy/drafts/1/decision", json={"approve": False, "preview": True})
    assert r.status_code == 422


def test_the_sample_document_is_served():
    r = local().get("/api/policy/intake/sample")
    assert r.status_code == 200 and r.content.startswith(b"%PDF-") and r.headers["content-type"] == "application/pdf"


@pytest.fixture
def scratch(admin_conn, embeddings, settings):
    name = f"ASOF_A{uuid.uuid4().hex[:6].upper()}"
    schema.install(admin_conn, name)
    seed.seed_policy(admin_conn, embeddings, name)
    seed.seed_chain_head(admin_conn, name)
    seed.seed_published_answers(admin_conn, name)
    seed.seed_faq(admin_conn, embeddings, name)
    schema.apply_grants(admin_conn, settings.asof_app_user, settings.asof_editor_user, name)
    yield name
    schema.drop(admin_conn, name)


@pytest.mark.db2
def test_from_pdf_to_preview_to_versions_in_force(settings, scratch):
    c = local(settings, schema_name=scratch)
    r = pdf_post(c)
    assert r.status_code == 200, r.text
    draft = r.json()["draft"]
    assert draft["status"] == "PENDING" and [i["kind"] for i in draft["items_detail"]] == ["CHANGE", "CHANGE"]
    assert draft["items_detail"][0]["current"]["version"] == "v2"
    did = draft["draft_id"]
    assert c.get(f"/api/policy/drafts/{did}/source").content == PDF
    assert any(d["draft_id"] == did for d in c.get("/api/policy/drafts").json())

    preview = c.post(f"/api/policy/drafts/{did}/decision", json={"approve": True, "accept": [1, 2], "preview": True}).json()
    assert preview["preview"] and preview["draft"]["status"] == "PENDING" and "BAG-001" in preview["impact"]

    done = c.post(f"/api/policy/drafts/{did}/decision", json={"approve": True, "accept": [1, 2]})
    assert done.status_code == 200 and done.json()["draft"]["status"] == "APPLIED"
    assert [a["version"] for a in done.json()["applied"]] == ["v3", "v2"]
    again = c.post(f"/api/policy/drafts/{did}/decision", json={"approve": False})
    assert again.status_code == 409
    assert c.get("/api/policy/drafts/999999").status_code == 404
    bag = next(x for x in c.get("/api/policy/timeline?doc_id=AURELIA-CSP").json() if x["clause_id"] == "BAG-001")
    assert bag["versions"][-1]["version"] == "v3" and bag["versions"][-1]["changed_by"] == settings.asof_editor_user.upper()
