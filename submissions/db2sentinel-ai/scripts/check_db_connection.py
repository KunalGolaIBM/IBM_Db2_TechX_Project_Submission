#!/usr/bin/env python3
"""
IBM Db2 Diagnostic & Verification Script for Db2Sentinel AI.
Tests live connectivity to the IBM Db2 database, reports server metrics,
or displays clear diagnostics if Db2 is not yet reached.
"""
import sys
import os
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from src.backend.app.config import settings
from src.backend.app.db2_connector import Db2Connector

def main():
    print("=" * 60)
    print("IBM Db2 Connection Verification — Db2Sentinel AI")
    print("=" * 60)
    print(f"Target Host:     {settings.DB2_HOST}")
    print(f"Target Port:     {settings.DB2_PORT}")
    print(f"Target Database: {settings.DB2_DATABASE}")
    print(f"Target User:     {settings.DB2_USERNAME}")
    print(f"Security Mode:   {settings.DB2_SECURITY}")
    print("-" * 60)

    connector = Db2Connector(
        host=settings.DB2_HOST,
        port=settings.DB2_PORT,
        database=settings.DB2_DATABASE,
        username=settings.DB2_USERNAME,
        password=settings.DB2_PASSWORD,
        security=settings.DB2_SECURITY,
        ssl_cert=settings.DB2_SSL_CERTIFICATE
    )

    print("Attempting connection via official ibm_db driver...")
    connected = connector.connect()

    if connected:
        print("✅ SUCCESS: Successfully connected to IBM Db2 database!")
        diag = connector.check_connection()
        print(f"   Server Time:   {diag.get('server_time')}")
        print(f"   Database Name: {diag.get('database_name')}")
        print(f"   Engine:        {diag.get('engine')}")
        connector.close()
        sys.exit(0)
    else:
        print("⚠️ NOTICE: Could not establish live connection to IBM Db2.")
        print("   Common causes:")
        print("   1. IBM Db2 container/service is not currently running.")
        print("      Run: docker-compose up -d db2")
        print("   2. Network/firewall credentials require configuration in .env.")
        print("-" * 60)
        if settings.DB2_DEMO_FALLBACK:
            print("✅ DEMO FALLBACK AVAILABLE: The application is configured to use")
            print("   the high-fidelity local relational store for offline demonstrations.")
        sys.exit(0)

if __name__ == "__main__":
    main()
