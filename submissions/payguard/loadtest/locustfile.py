"""Repeatable text screening workload. No external AI calls; real app + Db2.

locust -f loadtest/locustfile.py --headless -u 50 -r 10 -t 60s \
    --host http://127.0.0.1:8000 --csv .artifacts/before
"""
import itertools
import json
from pathlib import Path

from locust import HttpUser, events, task

MESSAGES = [
    {"message": "Abeg send your OTP and BVN make we upgrade your bank account."},
    {"message": "Pay registration fee of N5000 before you collect the job."},
    {"message": "Send as friends and family, only 2 left, pay now.", "payment_method": "friends_family"},
    {"message": "Transfer to OPay 0000012345, account name is different but don't mind."},
    {"message": "Your parcel needs a customs clearance fee before delivery."},
    {"message": "Double your money, guaranteed weekly returns, deposit USDT."},
    {"message": "Order for three textbooks confirmed. Invoice attached, pickup Saturday."},
    {"message": "Abeg your clothes don ready. You fit collect am for shop tomorrow."},
    {"message": "Pay for the rice after inspecting it at the store. Delivery included."},
    {"message": "Thank you for shopping with us. Keep your receipt for delivery."},
]


class Buyer(HttpUser):
    def on_start(self):
        self.messages = itertools.cycle(MESSAGES)

    @task
    def screen(self):
        with self.client.post("/api/screen", json={**next(self.messages), "region": "NG", "explain": False},
                              catch_response=True, name="/api/screen") as response:
            if response.status_code == 200:
                body = response.json()
                if body.get("verdict") not in {"ALLOW", "REVIEW", "BLOCK"} or body.get("degraded"):
                    response.failure("Missing verdict or degraded response")


@events.quitting.add_listener
def save_final_summary(environment, **kwargs):
    """Capture final statistics; periodic CSV can lag the last console output."""
    stats = environment.stats.total
    summary = {"requests": stats.num_requests, "failures": stats.num_failures,
               "requests_per_second": stats.total_rps,
               "p50_ms": stats.get_response_time_percentile(0.5),
               "p95_ms": stats.get_response_time_percentile(0.95),
               "average_ms": stats.avg_response_time}
    prefix = environment.parsed_options.csv_prefix
    if prefix:
        target = Path(prefix + "_summary.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    if stats.num_failures:
        environment.process_exit_code = 1
