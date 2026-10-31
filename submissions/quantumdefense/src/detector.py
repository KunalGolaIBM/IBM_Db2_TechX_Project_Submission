
from ipaddress import ip_address

from storage import save_event, save_alert


SUSPICIOUS_EVENTS = {
    "brute_force": "High",
    "sql_injection": "Critical",
    "port_scan": "Medium",
    "unauthorized_access": "High",
    "malware_detected": "Critical"
}


def analyze_event(event):
    event_type = str(event.get("event_type", "")).strip().lower()

    if not event_type:
        raise ValueError("Event type is required")

    if event_type in SUSPICIOUS_EVENTS:
        severity = SUSPICIOUS_EVENTS[event_type]

        return {
            "detected": True,
            "severity": severity,
            "message": f"Suspicious activity detected: {event_type}"
        }

    return {
        "detected": False,
        "severity": "Low",
        "message": "No suspicious activity identified"
    }


def process_event(event):
    event_type = str(event.get("event_type", "")).strip().lower()
    source_ip = str(event.get("source_ip", "")).strip()
    description = str(event.get("description", "")).strip()

    if not source_ip:
        raise ValueError("Source IP address is required")

    try:
        ip_address(source_ip)
    except ValueError:
        raise ValueError("Invalid source IP address")

    result = analyze_event({
        **event,
        "event_type": event_type
    })

    event_data = {
        "event_type": event_type,
        "source_ip": source_ip,
        "severity": result["severity"],
        "description": description or result["message"]
    }

    event_id = save_event(event_data)

    if result["detected"]:
        save_alert(event_id, result["message"])

    return {
        "event_id": event_id,
        **result
    }
