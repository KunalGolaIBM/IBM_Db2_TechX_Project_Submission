
import os
import ipaddress

from flask import (
    Flask, render_template, request,
    redirect, url_for, flash, session
)
from dotenv import load_dotenv

load_dotenv()

from storage import (
    initialize_storage,
    get_events,
    get_alerts,
    save_ml_result,
    get_ml_results
)
from detector import process_event
from analyzer import analyze_network_activity

app = Flask(__name__)
app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    "development-only-key"
)

initialize_storage()


@app.route("/")
def dashboard():
    events = get_events()
    alerts = get_alerts()
    ml_results = get_ml_results()

    total_events = len(events)
    total_alerts = len(alerts)

    critical_alerts = sum(
        1 for event in events
        if event["severity"] == "Critical"
    )

    return render_template(
        "index.html",
        events=events,
        alerts=alerts,
        ml_results=ml_results,
        total_events=total_events,
        total_alerts=total_alerts,
        critical_alerts=critical_alerts,
        latest_analysis=session.get("latest_analysis")
    )


@app.route("/simulate", methods=["POST"])
def simulate_event():
    event_type = request.form.get(
        "event_type", ""
    ).strip().lower()

    source_ip = request.form.get(
        "source_ip", ""
    ).strip()

    description = request.form.get(
        "description", ""
    ).strip()

    allowed_events = {
        "normal_activity",
        "brute_force",
        "sql_injection",
        "port_scan",
        "unauthorized_access",
        "malware_detected"
    }

    if event_type not in allowed_events:
        flash("Invalid event type.", "error")
        return redirect(url_for("dashboard"))

    try:
        ipaddress.ip_address(source_ip)
    except ValueError:
        flash("Please enter a valid IP address.", "error")
        return redirect(url_for("dashboard"))

    event = {
        "event_type": event_type,
        "source_ip": source_ip,
        "description": description or event_type.replace("_", " ")
    }

    # Rule-based detection and event storage
    result = process_event(event)

    # Illustrative metrics for the ML prototype
    ml_metrics = {
        "normal_activity": (1, 12, 0),
        "brute_force": (100, 20, 1),
        "sql_injection": (5, 30, 2),
        "port_scan": (2, 150, 25),
        "unauthorized_access": (10, 40, 3),
        "malware_detected": (20, 200, 15)
    }

    failed_logins, connections, unusual_ports = (
        ml_metrics[event_type]
    )

    # Machine-learning analysis
    ml_result = analyze_network_activity(
        failed_logins,
        connections,
        unusual_ports
    )

    # Permanently save ML result
    save_ml_result(
        result["event_id"],
        ml_result
    )

    # Display latest result
    session["latest_analysis"] = {
        "event_type": event_type,
        "source_ip": source_ip,
        "rule_severity": result["severity"],
        "rule_detected": result["detected"],
        "anomaly_detected": ml_result["anomaly_detected"],
        "anomaly_score": round(
            ml_result["anomaly_score"], 4
        ),
        "method": ml_result["method"]
    }

    flash("Security event and ML analysis saved successfully.", "success")

    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
