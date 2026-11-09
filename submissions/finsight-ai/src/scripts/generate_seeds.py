#!/usr/bin/env python3
"""
FinSight AI — Synthetic Financial Seed Data Generator
Generates realistic, deterministic financial records spanning 6 months (June 2026 - Nov 2026).
Ensures idempotency with Db2 MERGE statements.
"""

from datetime import date, timedelta

USER_ID = "usr_demo_synthetic_01"
USER_EMAIL = "alex.chen.demo@finsight.internal"
USER_NAME = "Alex Chen (Synthetic Demo)"

ACCOUNTS = [
    ("acc_checking_01", USER_ID, "Premier Checking", "CHECKING", "HDFC Bank", "INR", 25000.00),
    ("acc_savings_01", USER_ID, "High-Yield Savings", "SAVINGS", "ICICI Bank", "INR", 150000.00),
    ("acc_credit_01", USER_ID, "Millennia Credit Card", "CREDIT_CARD", "HDFC Bank", "INR", 0.00),
]

CATEGORIES = [
    ("cat_salary", None, "Salary & Wages", "INCOME"),
    ("cat_freelance", None, "Consulting & Freelance", "INCOME"),
    ("cat_investment", None, "Investment Returns", "INCOME"),
    ("cat_groceries", None, "Groceries & Supermarket", "EXPENSE"),
    ("cat_dining", None, "Dining & Takeout", "EXPENSE"),
    ("cat_utilities", None, "Utilities & Internet", "EXPENSE"),
    ("cat_rent", None, "Housing & Rent", "EXPENSE"),
    ("cat_subscriptions", None, "Software & Subscriptions", "EXPENSE"),
    ("cat_travel", None, "Commute & Travel", "EXPENSE"),
    ("cat_shopping", None, "Electronics & Shopping", "EXPENSE"),
    ("cat_healthcare", None, "Healthcare & Pharmacy", "EXPENSE"),
    ("cat_transfer", None, "Internal Account Transfer", "TRANSFER"),
]

def generate_transactions():
    txs = []
    tx_counter = 1

    start_date = date(2026, 6, 1)
    end_date = date(2026, 11, 6)

    # 1. Monthly recurring: Salary on 1st of each month
    cur = start_date
    while cur <= end_date:
        if cur.day == 1:
            txs.append({
                "id": f"tx_sal_{cur.strftime('%Y%m')}",
                "acc": "acc_checking_01",
                "cat": "cat_salary",
                "ext": f"SAL-PAYROLL-{cur.strftime('%Y%m')}-9821",
                "merchant": "Acme Global Tech Payroll",
                "desc": "Monthly engineering salary credit",
                "amount": 125000.00,
                "type": "CREDIT",
                "date": cur.isoformat(),
                "status": "POSTED",
                "source": "BANK_SYNC"
            })
            # Monthly savings transfer on 2nd
            txs.append({
                "id": f"tx_sav_trf_{cur.strftime('%Y%m')}",
                "acc": "acc_checking_01",
                "cat": "cat_transfer",
                "ext": f"TRF-SAVINGS-{cur.strftime('%Y%m')}-4412",
                "merchant": "ICICI Savings Direct",
                "desc": "Automated monthly emergency fund transfer",
                "amount": 35000.00,
                "type": "DEBIT",
                "date": (cur + timedelta(days=1)).isoformat(),
                "status": "POSTED",
                "source": "BANK_SYNC"
            })
            # Monthly rent on 5th
            txs.append({
                "id": f"tx_rent_{cur.strftime('%Y%m')}",
                "acc": "acc_checking_01",
                "cat": "cat_rent",
                "ext": f"UPI-RENT-{cur.strftime('%Y%m')}-7723",
                "merchant": "Greenfield Living Properties",
                "desc": "Monthly apartment rent payment",
                "amount": 32000.00,
                "type": "DEBIT",
                "date": (cur + timedelta(days=4)).isoformat(),
                "status": "POSTED",
                "source": "BANK_SYNC"
            })
            # Monthly Utilities on 10th
            txs.append({
                "id": f"tx_wifi_{cur.strftime('%Y%m')}",
                "acc": "acc_credit_01",
                "cat": "cat_utilities",
                "ext": f"BILL-AIRTEL-{cur.strftime('%Y%m')}",
                "merchant": "Airtel Fiber Broadband",
                "desc": "Gigabit fiber home internet connection",
                "amount": 1199.00,
                "type": "DEBIT",
                "date": (cur + timedelta(days=9)).isoformat(),
                "status": "POSTED",
                "source": "CREDIT_CARD_SYNC"
            })
            txs.append({
                "id": f"tx_elec_{cur.strftime('%Y%m')}",
                "acc": "acc_checking_01",
                "cat": "cat_utilities",
                "ext": f"BILL-BSES-{cur.strftime('%Y%m')}",
                "merchant": "BSES Power Distribution",
                "desc": "Monthly domestic electricity consumption",
                "amount": 2480.00,
                "type": "DEBIT",
                "date": (cur + timedelta(days=11)).isoformat(),
                "status": "POSTED",
                "source": "BANK_SYNC"
            })
            # Subscriptions on 15th
            txs.append({
                "id": f"tx_sub_nflx_{cur.strftime('%Y%m')}",
                "acc": "acc_credit_01",
                "cat": "cat_subscriptions",
                "ext": f"SUB-NETFLIX-{cur.strftime('%Y%m')}",
                "merchant": "Netflix India",
                "desc": "Premium 4K Family Plan monthly subscription",
                "amount": 649.00,
                "type": "DEBIT",
                "date": (cur + timedelta(days=14)).isoformat(),
                "status": "POSTED",
                "source": "CREDIT_CARD_SYNC"
            })
            txs.append({
                "id": f"tx_sub_spot_{cur.strftime('%Y%m')}",
                "acc": "acc_credit_01",
                "cat": "cat_subscriptions",
                "ext": f"SUB-SPOTIFY-{cur.strftime('%Y%m')}",
                "merchant": "Spotify India",
                "desc": "Individual Premium Audio streaming",
                "amount": 119.00,
                "type": "DEBIT",
                "date": (cur + timedelta(days=14)).isoformat(),
                "status": "POSTED",
                "source": "CREDIT_CARD_SYNC"
            })
            txs.append({
                "id": f"tx_sub_gh_{cur.strftime('%Y%m')}",
                "acc": "acc_credit_01",
                "cat": "cat_subscriptions",
                "ext": f"SUB-GITHUB-{cur.strftime('%Y%m')}",
                "merchant": "GitHub Inc.",
                "desc": "GitHub Copilot Pro monthly developer plan",
                "amount": 850.00,
                "type": "DEBIT",
                "date": (cur + timedelta(days=15)).isoformat(),
                "status": "POSTED",
                "source": "CREDIT_CARD_SYNC"
            })
            txs.append({
                "id": f"tx_sub_aws_{cur.strftime('%Y%m')}",
                "acc": "acc_credit_01",
                "cat": "cat_subscriptions",
                "ext": f"SUB-AWS-{cur.strftime('%Y%m')}",
                "merchant": "Amazon Web Services",
                "desc": "Cloud hosting development instances",
                "amount": 1420.00,
                "type": "DEBIT",
                "date": (cur + timedelta(days=16)).isoformat(),
                "status": "POSTED",
                "source": "CREDIT_CARD_SYNC"
            })
        cur += timedelta(days=1)

    # 2. Frequent grocery, commute, and dining transactions across weeks
    merchants_groceries = [
        ("Blinkit Express", 1340.00, "Weekly groceries and dairy staples"),
        ("Zepto Quick Commerce", 820.00, "Fresh vegetables and sourdough bread"),
        ("Nature's Basket", 3150.00, "Artisanal cheeses, olive oil, and organic grains"),
        ("BigBasket Organic", 2490.00, "Monthly household cleaning & dry provisions"),
    ]

    merchants_dining = [
        ("Blue Tokai Coffee Roasters", 420.00, "Cold brew and almond croissant"),
        ("Starbucks Coffee", 580.00, "Caffe latte and roasted bagel"),
        ("Swiggy Gourmet", 1250.00, "Dinner delivery from Burma Burma"),
        ("Zomato Delivery", 890.00, "Woodfired sourdough pizza and salad"),
    ]

    merchants_commute = [
        ("Uber India", 480.00, "Premier cab to tech innovation campus"),
        ("Uber India", 360.00, "Afternoon return cab from client meeting"),
        ("Ola Cabs", 290.00, "Cab ride to metro interchange"),
    ]

    cur = start_date
    day_idx = 0
    while cur <= end_date:
        # Every 3 days: commute
        if cur.weekday() in (0, 2, 4):  # Mon, Wed, Fri
            m, amt, desc = merchants_commute[day_idx % len(merchants_commute)]
            txs.append({
                "id": f"tx_comm_{cur.strftime('%Y%m%d')}_{day_idx}",
                "acc": "acc_credit_01",
                "cat": "cat_travel",
                "ext": f"RIDE-{cur.strftime('%Y%m%d')}-{day_idx}",
                "merchant": m,
                "desc": desc,
                "amount": amt,
                "type": "DEBIT",
                "date": cur.isoformat(),
                "status": "POSTED",
                "source": "CREDIT_CARD_SYNC"
            })

        # Every 4 days: groceries
        if cur.day % 4 == 0:
            m, amt, desc = merchants_groceries[day_idx % len(merchants_groceries)]
            txs.append({
                "id": f"tx_groc_{cur.strftime('%Y%m%d')}_{day_idx}",
                "acc": "acc_checking_01",
                "cat": "cat_groceries",
                "ext": f"UPI-GROC-{cur.strftime('%Y%m%d')}-{day_idx}",
                "merchant": m,
                "desc": desc,
                "amount": amt,
                "type": "DEBIT",
                "date": cur.isoformat(),
                "status": "POSTED",
                "source": "BANK_SYNC"
            })

        # Weekends: dining out or delivery
        if cur.weekday() in (5, 6):  # Sat, Sun
            m, amt, desc = merchants_dining[day_idx % len(merchants_dining)]
            txs.append({
                "id": f"tx_dine_{cur.strftime('%Y%m%d')}_{day_idx}",
                "acc": "acc_credit_01",
                "cat": "cat_dining",
                "ext": f"POS-DINE-{cur.strftime('%Y%m%d')}-{day_idx}",
                "merchant": m,
                "desc": desc,
                "amount": amt,
                "type": "DEBIT",
                "date": cur.isoformat(),
                "status": "POSTED",
                "source": "CREDIT_CARD_SYNC"
            })

        cur += timedelta(days=1)
        day_idx += 1

    # 3. Deliberately unusual / anomaly transactions for anomaly intelligence testing
    txs.append({
        "id": "tx_anom_01_luxury_spike",
        "acc": "acc_credit_01",
        "cat": "cat_shopping",
        "ext": "TXN-INTR-901844",
        "merchant": "Luxury Electronics Dubai FZE",
        "desc": "High-ticket foreign transaction for mirrorless cinema camera",
        "amount": 84500.00,
        "type": "DEBIT",
        "date": "2026-09-18",
        "status": "POSTED",
        "source": "CREDIT_CARD_SYNC"
    })

    txs.append({
        "id": "tx_anom_02_velocity_1",
        "acc": "acc_checking_01",
        "cat": "cat_shopping",
        "ext": "FASTPAY-GW-110291",
        "merchant": "FastPay Cash Gateway",
        "desc": "Unusual high-speed payout test charge 1 of 3",
        "amount": 9999.00,
        "type": "DEBIT",
        "date": "2026-10-04",
        "status": "POSTED",
        "source": "BANK_SYNC"
    })
    txs.append({
        "id": "tx_anom_02_velocity_2",
        "acc": "acc_checking_01",
        "cat": "cat_shopping",
        "ext": "FASTPAY-GW-110292",
        "merchant": "FastPay Cash Gateway",
        "desc": "Unusual high-speed payout test charge 2 of 3",
        "amount": 9999.00,
        "type": "DEBIT",
        "date": "2026-10-04",
        "status": "POSTED",
        "source": "BANK_SYNC"
    })
    txs.append({
        "id": "tx_anom_02_velocity_3",
        "acc": "acc_checking_01",
        "cat": "cat_shopping",
        "ext": "FASTPAY-GW-110293",
        "merchant": "FastPay Cash Gateway",
        "desc": "Unusual high-speed payout test charge 3 of 3",
        "amount": 9999.00,
        "type": "DEBIT",
        "date": "2026-10-04",
        "status": "POSTED",
        "source": "BANK_SYNC"
    })

    txs.append({
        "id": "tx_anom_03_subscription_jump",
        "acc": "acc_credit_01",
        "cat": "cat_subscriptions",
        "ext": "SUB-AWS-SPIKE-1028",
        "merchant": "Amazon Web Services",
        "desc": "Unexpected 30x cost drift spike due to runaway GPU instance cluster",
        "amount": 42800.00,
        "type": "DEBIT",
        "date": "2026-10-28",
        "status": "POSTED",
        "source": "CREDIT_CARD_SYNC"
    })

    # Enforce date integrity: All transactions strictly after 2026-11-07 are marked PENDING (scheduled future bills)
    as_of_date = date(2026, 11, 7)
    for t in txs:
        t_date = date.fromisoformat(t["date"])
        if t_date > as_of_date:
            t["status"] = "PENDING"
        else:
            t["status"] = "POSTED"

    return txs

def main():
    txs = generate_transactions()
    print(f"Generated {len(txs)} synthetic transactions.")

    lines = []
    lines.append("-- ==============================================================================")
    lines.append("-- Seed Script: 001_synthetic_demo_seed.sql")
    lines.append("-- Description: Populates synthetic demo user, accounts, categories, and >100")
    lines.append("--              realistic financial transactions with idempotent MERGE statements.")
    lines.append("-- ==============================================================================\n")

    # 1. User
    lines.append(f"""MERGE INTO FINSIGHT.USERS AS target
USING (VALUES ('{USER_ID}', '{USER_EMAIL}', '{USER_NAME}')) AS src (user_id, email, full_name)
ON (target.user_id = src.user_id)
WHEN NOT MATCHED THEN
    INSERT (user_id, email, full_name)
    VALUES (src.user_id, src.email, src.full_name);
""")

    # 2. Accounts
    for acc_id, u_id, acc_name, acc_type, inst, curr, bal in ACCOUNTS:
        lines.append(f"""MERGE INTO FINSIGHT.ACCOUNTS AS target
USING (VALUES ('{acc_id}', '{u_id}', '{acc_name}', '{acc_type}', '{inst}', '{curr}', {bal:.2f}))
AS src (account_id, user_id, account_name, account_type, institution_name, currency, opening_balance)
ON (target.account_id = src.account_id)
WHEN NOT MATCHED THEN
    INSERT (account_id, user_id, account_name, account_type, institution_name, currency, opening_balance)
    VALUES (src.account_id, src.user_id, src.account_name, src.account_type, src.institution_name, src.currency, src.opening_balance);
""")

    # 3. Categories
    for cat_id, u_id, cat_name, cat_type in CATEGORIES:
        u_val = f"'{u_id}'" if u_id else "CAST(NULL AS VARCHAR(36))"
        lines.append(f"""MERGE INTO FINSIGHT.CATEGORIES AS target
USING (VALUES ('{cat_id}', {u_val}, '{cat_name}', '{cat_type}'))
AS src (category_id, user_id, category_name, category_type)
ON (target.category_id = src.category_id)
WHEN NOT MATCHED THEN
    INSERT (category_id, user_id, category_name, category_type)
    VALUES (src.category_id, src.user_id, src.category_name, src.category_type);
""")

    # 4. Transactions
    for t in txs:
        desc_escaped = t['desc'].replace("'", "''")
        lines.append(f"""MERGE INTO FINSIGHT.TRANSACTIONS AS target
USING (VALUES ('{t['id']}', '{USER_ID}', '{t['acc']}', '{t['cat']}', '{t['ext']}', '{t['merchant']}', '{desc_escaped}', {t['amount']:.2f}, 'INR', '{t['type']}', DATE('{t['date']}'), '{t['status']}', '{t['source']}'))
AS src (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
ON (target.transaction_id = src.transaction_id)
WHEN MATCHED THEN
    UPDATE SET target.transaction_status = src.transaction_status
WHEN NOT MATCHED THEN
    INSERT (transaction_id, user_id, account_id, category_id, external_transaction_id, merchant, description, amount, currency, transaction_type, transaction_date, transaction_status, source)
    VALUES (src.transaction_id, src.user_id, src.account_id, src.category_id, src.external_transaction_id, src.merchant, src.description, src.amount, src.currency, src.transaction_type, src.transaction_date, src.transaction_status, src.source);
""")

    # 5. Pre-computed anomaly alerts for the deliberate anomalies
    anomalies = [
        ("alt_01", USER_ID, "tx_anom_01_luxury_spike", "AMOUNT_SPIKE", "HIGH",
         "Single transaction of INR 84,500.00 is 14.8x standard deviation above the 90-day shopping average (INR 2,850.00). Unfamiliar foreign merchant detected.", 94.50),
        ("alt_02", USER_ID, "tx_anom_02_velocity_1", "VELOCITY_SPIKE", "CRITICAL",
         "Rapid velocity burst: 3 consecutive transactions of INR 9,999.00 executed within 10 minutes against payment gateway 'FastPay Cash Gateway'.", 98.20),
        ("alt_03", USER_ID, "tx_anom_03_subscription_jump", "RECURRING_DRIFT", "HIGH",
         "Recurring software cost drift: Amazon Web Services billed INR 42,800.00, representing a 3,014% surge compared to historic monthly baseline of INR 1,420.00.", 91.00),
    ]

    for alt_id, u_id, tx_id, a_type, sev, expl, score in anomalies:
        expl_escaped = expl.replace("'", "''")
        lines.append(f"""MERGE INTO FINSIGHT.ANOMALY_ALERTS AS target
USING (VALUES ('{alt_id}', '{u_id}', '{tx_id}', '{a_type}', '{sev}', '{expl_escaped}', {score:.2f}, 'ACTIVE'))
AS src (alert_id, user_id, transaction_id, alert_type, severity, explanation, score, status)
ON (target.alert_id = src.alert_id)
WHEN NOT MATCHED THEN
    INSERT (alert_id, user_id, transaction_id, alert_type, severity, explanation, score, status)
    VALUES (src.alert_id, src.user_id, src.transaction_id, src.alert_type, src.severity, src.explanation, src.score, src.status);
""")

    with open("database/seeds/001_synthetic_demo_seed.sql", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("Saved to database/seeds/001_synthetic_demo_seed.sql")

if __name__ == "__main__":
    main()
