# HumanityChain Production Deployment Checklist

## 1) Security gate (must pass)
- [ ] External smart-contract audit completed (`contracts/HumanityHub.sol`, `contracts/HumanitySpoke.sol`)
- [ ] Critical/high findings remediated and re-validated
- [ ] Bug bounty program published (`SECURITY.md`)

## 2) CI/CD gate
- [x] Backend CI tests pass (`pytest -q backend/test_humanity_api.py`)
- [x] Backend compile check passes (`python -m py_compile backend/main.py`)
- [x] Contract tests pass (`forge test -vv`)
- [ ] Release tag created and changelog published

## 3) Runtime configuration
- [ ] `API_SECRET_KEY` rotated for production
- [ ] `HUMANITY_ALLOWED_TARGET_CHAINS` set for production domains
- [ ] `HUMANITY_IP_RATE_LIMIT_*` and `HUMANITY_RATE_LIMIT_*` tuned by load tests
- [ ] Backup/restore policy for `HUMANITY_DB_PATH` validated

## 4) Operational readiness
- [x] Monitoring runbook available (`backend/monitoring_runbook.md`)
- [ ] Alerts connected to on-call channel
- [ ] Incident commander + escalation policy assigned

## 5) Go-live checks
- [x] Smoke test script agregado: `backend/smoke_test_humanity.py` (health/metrics/state flow).
- [x] End-to-end workflow cubierto en tests y smoke script (`queued -> sent -> acknowledged -> finalized`).
- [ ] Rollback drill executed and documented
