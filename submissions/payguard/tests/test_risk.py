from risk import RiskEngine, ScreenRequest


def screen(repo, embedder, **kw):
    return RiskEngine(repo, embedder).screen(ScreenRequest(**kw))


def test_trusted_merchant_is_allowed(repo, embedder):
    r = screen(repo, embedder, merchant="Uyo Gadgets Ltd", payee_email="sales@uyo-gadgets.example", amount=320,
               message="Your order #1043 Samsung A55 is confirmed, invoice attached, delivery in 2 days.")
    assert r.verdict == "ALLOW", r.reasons
    assert any(x["code"] == "TRUSTED_ENTITY" for x in r.reasons)


def test_blocklisted_friends_family_seller_is_blocked(repo, embedder):
    r = screen(repo, embedder, merchant="FastDeals NG", payee_email="fastdeals.ng@mail.example", amount=210,
               payment_method="friends_family",
               message="PS5 brand new, only 2 left. Send it as friends and family to avoid fees, chat on WhatsApp.")
    assert r.verdict == "BLOCK" and r.risk_score >= 85
    assert r.screening_id == 1
    sources = {x["source"] for x in r.reasons}
    assert {"rule", "db2_entity"} <= sources


def test_unknown_phishing_message_blocked_by_rules_and_vectors(repo, embedder):
    r = screen(repo, embedder, merchant="PayPal Security", payee_email="", amount=0,
               message="Your PayPal account has been limited due to unusual activity. Verify your account at "
                       "https://paypa1-secure.example within 24 hours.")
    assert r.verdict == "BLOCK"
    assert any(x["code"] == "LOOKALIKE_DOMAIN" for x in r.reasons)
    assert r.matched_patterns[0]["category"] in ("phishing", "impersonation")


def test_new_job_scam_matches_vector_playbook(repo, embedder):
    r = screen(repo, embedder, merchant="Remote Hire", payee_email="hr@mail.example", amount=30, payment_method="wire",
               message="You are selected for data entry work from home, earn daily. Pay registration fee to start training.")
    assert r.verdict in ("REVIEW", "BLOCK")
    assert any(x["source"] == "db2_vector" for x in r.reasons)


def test_velocity_from_history(repo, embedder):
    for _ in range(2):
        screen(repo, embedder, merchant="X", payee_email="new@mail.example", amount=50, payment_method="gift_card",
               message="Buy steam gift cards and send the codes")
    r = screen(repo, embedder, merchant="X", payee_email="new@mail.example", amount=50, message="hello")
    assert any(x["code"] == "RECENT_BLOCKS" for x in r.reasons)


def test_community_reports_auto_escalate(repo, embedder):
    for _ in range(3):
        eid = repo.upsert_entity("phone", "07000000999", "SUSPECT")
    assert repo.lookup_entities([("phone", "07000000999")])[0]["status"] == "BLOCKED"
    assert eid
