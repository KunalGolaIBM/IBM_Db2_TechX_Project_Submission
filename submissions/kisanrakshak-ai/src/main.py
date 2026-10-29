#!/usr/bin/env python3

from __future__ import annotations

import os
from typing import Any, Dict, List

from db2_client import build_sample_output, fetch_field_summary, generate_recommendation, get_connection, ensure_schema, seed_demo_records


def main() -> None:
    print("KisanRakshak AI - IBM Db2 advisory demo")
    print("=" * 50)

    try:
        conn = get_connection()
        ensure_schema(conn)
        seed_demo_records(conn)
        fields = fetch_field_summary(conn)
    except Exception as exc:
        print(f"Db2 connection unavailable: {exc}")
        print("Falling back to demo data for submission demonstration.")
        fields = build_sample_output()

    if not fields:
        fields = build_sample_output()

    recommendations: List[Dict[str, Any]] = []
    for field in fields:
        advice = generate_recommendation(field)
        recommendations.append({"field": field, "advice": advice})

    for item in recommendations:
        field = item["field"]
        advice = item["advice"]
        print(f"Farmer: {field.get('FARMER_NAME', 'Unknown')}")
        print(f"Village: {field.get('VILLAGE', 'Unknown')}")
        print(f"Crop: {field.get('CROP', 'Unknown')}")
        print(f"Moisture: {field.get('MOISTURE_LEVEL', 'N/A')}%")
        print(f"Disease Risk: {field.get('DISEASE_RISK_SCORE', 'N/A')}/100")
        print(f"Recommendation: {advice['recommendation']}")
        print(f"Confidence: {advice['confidence_score']}")
        print("-" * 50)

    print("Application completed successfully.")


if __name__ == "__main__":
    main()
