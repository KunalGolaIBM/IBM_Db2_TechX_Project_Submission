from signals import extract_entities, lookalike_brand, run_rules


def codes(text):
    return {s.code for s in run_rules(text)}


def test_friends_and_family_detected():
    assert "FRIENDS_FAMILY" in codes("Please send it as friends and family to avoid fees")
    assert "FRIENDS_FAMILY" in codes("pay via F&F only")


def test_credentials_and_pidgin_context():
    assert "CREDENTIALS" in codes("Abeg read the OTP wey dem send to your phone")
    assert "CREDENTIALS" in codes("Your BVN will be blocked today")


def test_benign_message_has_no_rules():
    assert codes("Order #1043 Samsung A55 confirmed, invoice attached, delivery in 2 days") == set()


def test_entity_extraction():
    ex = extract_entities("Pay fastdeals.ng@mail.example or visit https://paypa1-verify.example/login, "
                          "call 0700 000 0101 or +234 700 000 0202. USDT to 0x1111111111111111111111111111111111111111",
                          "Seller@Shop.Example")
    assert "fastdeals.ng@mail.example" in ex.emails and "seller@shop.example" in ex.emails
    assert "paypa1-verify.example" in ex.domains
    assert "07000000101" in ex.phones and "07000000202" in ex.phones
    assert ex.wallets == ["0x1111111111111111111111111111111111111111"]
    assert "25.00" not in " ".join(ex.domains)


def test_lookalike_domains():
    assert lookalike_brand("paypa1-verify.example") == "paypal"
    assert lookalike_brand("paypalsecure.com") == "paypal"
    assert lookalike_brand("www.paypal.com") is None
    assert lookalike_brand("amazonaws.com") is None
    assert lookalike_brand("pineapple.com") is None
    assert lookalike_brand("uyo-gadgets.example") is None
