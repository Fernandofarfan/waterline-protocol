#!/usr/bin/env python3
"""Simple smoke test for HumanityChain endpoints.

Usage:
  API_KEY=... BASE_URL=http://localhost:8000 python backend/smoke_test_humanity.py
"""

import os
import sys
import requests

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "")
HEADERS = {"X-API-Key": API_KEY}

if not API_KEY:
    print("ERROR: API_KEY env var is required")
    sys.exit(2)


def call(method: str, path: str, **kwargs):
    url = f"{BASE_URL}{path}"
    resp = requests.request(method, url, headers=HEADERS, timeout=10, **kwargs)
    if resp.status_code >= 400:
        raise RuntimeError(f"{method} {path} failed: {resp.status_code} {resp.text}")
    return resp.json()


def main():
    h = call("GET", "/v1/humanity/health")
    assert h["status"] == "ok"

    payload = {
        "operation_id": 900001,
        "criticality_profile": "medical",
        "target_chains": ["hub"],
        "payload": {"smoke": True},
    }
    created = call("POST", "/v1/humanity/operation/update", json=payload)
    msg = created["data"]["message_id"]

    for state in ["sent", "acknowledged", "finalized"]:
        call("POST", "/v1/humanity/operation/state", json={"message_id": msg, "state": state})

    metrics = call("GET", "/v1/humanity/metrics")
    assert metrics["status"] == "ok"

    print("HumanityChain smoke test passed")


if __name__ == "__main__":
    main()
