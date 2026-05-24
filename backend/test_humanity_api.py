import asyncio
import tempfile
from pathlib import Path

import main as app_main


def setup_temp_logfile():
    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp.close()
    app_main.HUMANITY_LOG_FILE = Path(tmp.name)
    app_main.HUMANITY_DB_PATH = Path(tmp.name + ".db")
    app_main._init_humanity_db()
    app_main.HUMANITY_OPERATION_LOGS.clear()
    app_main._REQUEST_COUNTER.clear()
    app_main._IP_REQUEST_COUNTER.clear()
    app_main.RATE_LIMIT_MAX_REQUESTS = 1000
    app_main.IP_RATE_LIMIT_MAX_REQUESTS = 1000


def run(coro):
    return asyncio.run(coro)


def test_create_operation_success():
    setup_temp_logfile()
    payload = app_main.HumanityOperationUpdate(
        operation_id=1,
        criticality_profile="medical",
        target_chains=["hub"],
        payload={"foo": "bar"},
    )
    resp = run(app_main.humanity_operation_update(payload, api_key="test"))
    assert resp["status"] == "success"
    assert resp["data"]["state"] == "queued"
    assert len(app_main.HUMANITY_OPERATION_LOGS) == 1


def test_invalid_transition_rejected():
    setup_temp_logfile()
    create_payload = app_main.HumanityOperationUpdate(
        operation_id=2,
        criticality_profile="food",
        target_chains=["hub"],
        payload={},
    )
    create_resp = run(app_main.humanity_operation_update(create_payload, api_key="test"))
    message_id = create_resp["data"]["message_id"]

    state_update = app_main.HumanityOperationStateUpdate(message_id=message_id, state="finalized")
    try:
        run(app_main.humanity_operation_state(state_update, api_key="test"))
        assert False, "Expected transition conflict"
    except app_main.HTTPException as exc:
        assert exc.status_code == 409


def test_duplicate_target_chains_rejected():
    setup_temp_logfile()
    payload = app_main.HumanityOperationUpdate(
        operation_id=3,
        criticality_profile="medical",
        target_chains=["hub", "hub"],
        payload={},
    )
    try:
        run(app_main.humanity_operation_update(payload, api_key="test"))
        assert False, "Expected duplicate chain validation error"
    except app_main.HTTPException as exc:
        assert exc.status_code == 400


def test_payload_limit_rejected():
    setup_temp_logfile()
    app_main.MAX_PAYLOAD_BYTES = 30
    payload = app_main.HumanityOperationUpdate(
        operation_id=4,
        criticality_profile="medical",
        target_chains=["hub"],
        payload={"big": "x" * 100},
    )
    try:
        run(app_main.humanity_operation_update(payload, api_key="test"))
        assert False, "Expected payload limit error"
    except app_main.HTTPException as exc:
        assert exc.status_code == 413


def test_humanity_health_ok():
    setup_temp_logfile()
    resp = run(app_main.humanity_health(api_key="test"))
    assert resp["status"] == "ok"
    assert "allowed_target_chains" in resp


def test_operation_id_conflict_rejected():
    setup_temp_logfile()
    first = app_main.HumanityOperationUpdate(
        operation_id=10,
        criticality_profile="medical",
        target_chains=["hub"],
        payload={"a": 1},
    )
    run(app_main.humanity_operation_update(first, api_key="test"))

    second = app_main.HumanityOperationUpdate(
        operation_id=10,
        criticality_profile="medical",
        target_chains=["hub"],
        payload={"a": 2},
    )
    try:
        run(app_main.humanity_operation_update(second, api_key="test"))
        assert False, "Expected operation_id conflict"
    except app_main.HTTPException as exc:
        assert exc.status_code == 409


def test_timestamps_present():
    setup_temp_logfile()
    payload = app_main.HumanityOperationUpdate(
        operation_id=11,
        criticality_profile="food",
        target_chains=["hub"],
        payload={},
    )
    resp = run(app_main.humanity_operation_update(payload, api_key="test"))
    assert "created_at" in resp["data"]
    assert "updated_at" in resp["data"]


def test_operations_paginated():
    setup_temp_logfile()
    for i in range(20, 25):
        payload = app_main.HumanityOperationUpdate(
            operation_id=i,
            criticality_profile="standard",
            target_chains=["hub"],
            payload={"n": i},
        )
        run(app_main.humanity_operation_update(payload, api_key="test"))

    resp = run(app_main.humanity_operations_paginated(offset=2, limit=2, api_key="test"))
    assert resp["status"] == "success"
    assert resp["offset"] == 2
    assert resp["limit"] == 2
    assert len(resp["data"]) == 2


def test_persist_to_sqlite_db():
    setup_temp_logfile()
    payload = app_main.HumanityOperationUpdate(
        operation_id=50,
        criticality_profile="medical",
        target_chains=["hub"],
        payload={"x": 1},
    )
    run(app_main.humanity_operation_update(payload, api_key="test"))
    app_main.HUMANITY_OPERATION_LOGS.clear()
    app_main._REQUEST_COUNTER.clear()
    app_main._IP_REQUEST_COUNTER.clear()
    app_main.RATE_LIMIT_MAX_REQUESTS = 1000
    app_main.IP_RATE_LIMIT_MAX_REQUESTS = 1000
    app_main._load_humanity_from_db()
    assert len(app_main.HUMANITY_OPERATION_LOGS) == 1
    assert app_main.HUMANITY_OPERATION_LOGS[0]["operation_id"] == 50


def test_ip_rate_limit_rejected():
    setup_temp_logfile()
    app_main.IP_RATE_LIMIT_MAX_REQUESTS = 1

    payload = app_main.HumanityOperationUpdate(
        operation_id=60,
        criticality_profile="medical",
        target_chains=["hub"],
        payload={},
    )
    run(app_main.humanity_operation_update(payload, request=None, api_key="test"))

    payload2 = app_main.HumanityOperationUpdate(
        operation_id=61,
        criticality_profile="medical",
        target_chains=["hub"],
        payload={},
    )
    try:
        run(app_main.humanity_operation_update(payload2, request=None, api_key="test"))
        assert False, "Expected IP rate limit"
    except app_main.HTTPException as exc:
        assert exc.status_code == 429


def test_model_default_factories_are_isolated():
    a = app_main.HumanityOperationUpdate(operation_id=100, criticality_profile="medical")
    b = app_main.HumanityOperationUpdate(operation_id=101, criticality_profile="medical")
    a.target_chains.append("extra")
    a.payload["k"] = "v"
    assert b.target_chains == ["hub"]
    assert b.payload == {}


def test_humanity_metrics_endpoint():
    setup_temp_logfile()
    payload = app_main.HumanityOperationUpdate(
        operation_id=200,
        criticality_profile="medical",
        target_chains=["hub"],
        payload={},
    )
    run(app_main.humanity_operation_update(payload, api_key="test"))
    resp = run(app_main.humanity_metrics(api_key="test"))
    assert resp["status"] == "ok"
    assert resp["metrics"]["created"] >= 1


def test_operations_filter_endpoint():
    setup_temp_logfile()
    run(app_main.humanity_operation_update(app_main.HumanityOperationUpdate(operation_id=300, criticality_profile="medical", target_chains=["hub"], payload={}), api_key="test"))
    run(app_main.humanity_operation_update(app_main.HumanityOperationUpdate(operation_id=301, criticality_profile="food", target_chains=["hub"], payload={}), api_key="test"))

    resp = run(app_main.humanity_operations_filter(state="queued", criticality_profile="medical", api_key="test"))
    assert resp["status"] == "success"
    assert resp["count"] >= 1
    assert all(x["criticality_profile"] == "medical" for x in resp["data"])


def test_valid_full_state_transition_flow():
    setup_temp_logfile()
    create_payload = app_main.HumanityOperationUpdate(
        operation_id=400,
        criticality_profile="emergency",
        target_chains=["hub"],
        payload={"route": "A-B"},
    )
    create_resp = run(app_main.humanity_operation_update(create_payload, api_key="test"))
    message_id = create_resp["data"]["message_id"]

    sent = app_main.HumanityOperationStateUpdate(message_id=message_id, state="sent")
    ack = app_main.HumanityOperationStateUpdate(message_id=message_id, state="acknowledged")
    fin = app_main.HumanityOperationStateUpdate(message_id=message_id, state="finalized")

    r1 = run(app_main.humanity_operation_state(sent, api_key="test"))
    assert r1["data"]["state"] == "sent"
    r2 = run(app_main.humanity_operation_state(ack, api_key="test"))
    assert r2["data"]["state"] == "acknowledged"
    r3 = run(app_main.humanity_operation_state(fin, api_key="test"))
    assert r3["data"]["state"] == "finalized"
