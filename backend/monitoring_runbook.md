# HumanityChain Monitoring & Incident Runbook

## Core SLO targets
- API availability: 99.9%
- p95 latency (`/v1/humanity/*`): < 500ms
- Error rate (5xx): < 1%

## Minimum alerts
1. `rate_limited` spikes over baseline (possible abuse)
2. `replayed` spikes (possible duplicate storms)
3. sustained `failed` transitions
4. DB write failures in `persist_humanity_logs`

## Immediate response steps
1. Confirm endpoint health via `GET /v1/humanity/health` and `GET /v1/humanity/metrics`.
2. If abuse detected, lower `HUMANITY_IP_RATE_LIMIT_MAX_REQUESTS` and rotate API keys.
3. Pause spoke relayer operations on-chain if replay/mirror anomalies appear.
4. Export logs and preserve evidence for postmortem.

## Recovery checks
- Can create operation
- Can transition state queued->sent->acknowledged->finalized
- Metrics counters increasing as expected
- SQLite + JSON persistence both healthy
