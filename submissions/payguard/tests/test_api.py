import pytest
from fastapi.testclient import TestClient

import main
from analyst import UnsafeSQL, guard_sql


class FakePayPal:
    enabled = True

    def __init__(self):
        self.created = []

    def create_order(self, **kw):
        self.created.append(kw)
        return {"id": f"ORDER{len(self.created)}", "status": "CREATED"}

    def capture_order(self, order_id):
        return {"status": "COMPLETED", "purchase_units": [{"payments": {"captures": [{"id": "CAP1"}]}}],
                "payer": {"email_address": "buyer@example.com"}}


@pytest.fixture()
def client(repo, embedder):
    svc = main.Services(repo, embedder, FakePayPal())
    main.app.dependency_overrides[main.get_services] = lambda: svc
    yield TestClient(main.app), svc
    main.app.dependency_overrides.clear()


SAFE = {"merchant": "Akwa Books", "payee_email": "orders@akwa-books.example", "amount": 45,
        "message": "Three textbooks for CSC 301, invoice attached."}
SCAM = {"merchant": "FastDeals NG", "payee_email": "fastdeals.ng@mail.example", "amount": 210,
        "payment_method": "friends_family", "message": "send as friends and family, only 2 left"}


def test_screen_and_pay_safe(client):
    c, svc = client
    r = c.post("/api/screen", json=SAFE).json()
    assert r["verdict"] == "ALLOW" and r["paypal_allowed"]
    assert r["ai"]["mode"] == "rules"
    o = c.post("/api/paypal/orders", json={"screening_id": r["screening_id"]}).json()
    assert o["id"] == "ORDER1"
    assert svc.paypal.created[0]["amount"] == 45  # amount comes from Db2, not the browser
    cap = c.post(f"/api/paypal/orders/{o['id']}/capture", json={"screening_id": r["screening_id"]}).json()
    assert cap["status"] == "COMPLETED"
    assert svc.repo.get_screening(r["screening_id"])["paypal_status"] == "COMPLETED"


def test_blocked_payment_cannot_create_order(client):
    c, svc = client
    r = c.post("/api/screen", json=SCAM).json()
    assert r["verdict"] == "BLOCK" and not r["paypal_allowed"]
    resp = c.post("/api/paypal/orders", json={"screening_id": r["screening_id"]})
    assert resp.status_code == 403 and not svc.paypal.created


def test_capture_requires_matching_order(client):
    c, _ = client
    r = c.post("/api/screen", json=SAFE).json()
    assert c.post("/api/paypal/orders/FAKE/capture", json={"screening_id": r["screening_id"]}).status_code == 404


def test_agent_purchase_fallback_parser(client):
    c, _ = client
    r = c.post("/api/agent/purchase", json={"instruction": 'Pay $150 to ticketsplug@mail.example for 2 concert tickets, '
                                                           'they want friends and family only.'}).json()
    assert r["intent"]["amount"] == 150 and r["intent"]["payment_method"] == "friends_family"
    assert r["screening"]["verdict"] in ("REVIEW", "BLOCK")


def test_report_endpoint(client):
    c, _ = client
    body = {"entity_type": "email", "value": "Scammer@Mail.Example", "category": "phishing",
            "narrative": "Asked for my OTP pretending to be my bank"}
    r = c.post("/api/report", json=body).json()
    assert r["entity"]["entity_value"] == "scammer@mail.example" and r["entity"]["report_count"] == 1


def test_pidgin_fallback(client):
    c, _ = client
    r = c.post("/api/screen", json={**SCAM, "language": "pcm"}).json()
    assert "Abeg" in r["ai"]["summary"]


@pytest.mark.parametrize("sql", [
    "DELETE FROM PG_SCREENINGS",
    "SELECT * FROM PG_SCREENINGS; DROP TABLE PG_ENTITIES",
    "SELECT * FROM SYSCAT.TABLES",
    "SELECT EMBEDDING FROM PG_SCAM_PATTERNS",
    "UPDATE PG_ENTITIES SET STATUS='TRUSTED'",
])
def test_sql_guard_rejects(sql):
    with pytest.raises(UnsafeSQL):
        guard_sql(sql)


def test_sql_guard_accepts_and_limits():
    s = guard_sql("WITH B AS (SELECT * FROM PG_SCREENINGS WHERE VERDICT='BLOCK') "
                  "SELECT EXTRACT(DAY FROM CREATED_AT) AS D, COUNT(*) FROM B GROUP BY EXTRACT(DAY FROM CREATED_AT);")
    assert s.endswith("FETCH FIRST 100 ROWS ONLY")


def test_paste_only_extracts_amount_and_contacts(client):
    c, _ = client
    r = c.post("/api/screen", json={"message": "PS5 is $210. Send it as friends and family, or transfer to my OPay "
                                               "0000012345, account name is different but don't mind."}).json()
    assert r["amount"] == 210 and r["currency"] == "USD"
    assert "0000012345" in r["extracted"]["accounts"]
    assert r["plain"]["headline"] in ("Don't pay this seller", "Be careful before you pay")
    assert {"type": "account", "value": "0000012345"} in r["plain"]["reportable"]
    assert len(r["plain"]["reasons"]) <= 3


def test_platform_api_blocks_risky_new_seller(client):
    c, svc = client
    body = {"platform": "MarketSquare", "seller_name": "FastDeals NG", "seller_email": "fastdeals.ng@mail.example",
            "seller_account_age_days": 3, "listing_title": "PS5", "amount": 210, "market_price": 480,
            "payment_method": "friends_family",
            "chat": [{"sender": "seller", "text": "send it as friends and family, only 2 left"}]}
    r = c.post("/api/v1/checkout/verify", json=body).json()
    assert r["verdict"] == "BLOCK" and r["allow_payment"] is False
    assert c.post("/api/paypal/orders", json={"screening_id": r["screening_id"]}).status_code == 403


def test_platform_api_allows_trusted_seller(client):
    c, _ = client
    body = {"platform": "MarketSquare", "seller_name": "Akwa Books", "seller_email": "orders@akwa-books.example",
            "seller_account_age_days": 900, "listing_title": "Textbooks", "amount": 45, "market_price": 50,
            "chat": [{"sender": "seller", "text": "Please pay through the PayPal button so you are covered."}]}
    r = c.post("/api/v1/checkout/verify", json=body).json()
    assert r["verdict"] == "ALLOW" and r["allow_payment"] and r["paypal_allowed"]


def test_share_target_text_redirects_to_result(client):
    c, svc = client
    resp = c.post("/share", data={"text": "Your BVN will be blocked, read me the OTP now"}, follow_redirects=False)
    assert resp.status_code == 303 and resp.headers["location"].startswith("/?r=")
    rid = resp.headers["location"].split("=")[1]
    assert c.get(f"/api/results/{rid}").json()["verdict"] == "BLOCK"


def test_screenshot_without_ai_key_explains(client):
    c, _ = client
    r = c.post("/api/screen-image", files={"file": ("chat.png", b"\x89PNG fake", "image/png")})
    assert r.status_code == 503 and "paste" in r.json()["detail"].lower()


def test_screenshot_with_scripted_vision(client, monkeypatch):
    import vision
    c, _ = client
    monkeypatch.setattr(vision, "read_screenshot", lambda data, mime: {
        "platform": "WhatsApp", "seller_name": "Gadget Plug", "transcript": "Seller: pay registration fee to collect your prize",
        "phones": ["07000000202"], "emails": [], "links": [], "bank_accounts": ["0000012345"], "bank_names": ["OPay"],
        "wallets": [], "amount": 25, "currency": "USD", "payment_method": "wire", "is_payment_related": True})
    r = c.post("/api/screen-image", files={"file": ("chat.png", b"img", "image/png")}).json()
    assert r["source"] == "screenshot" and r["screenshot"]["seller_name"] == "Gadget Plug"
    assert r["verdict"] == "BLOCK"  # blocked OPay account from the knowledge base
