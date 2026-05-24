# Security Policy

## Reporting a Vulnerability
Please report security issues privately to maintainers before public disclosure.

Include:
- affected component (`backend`, `contracts`, `CI`)
- reproduction steps
- expected impact
- suggested mitigation (if available)

## Hardening Checklist
- [x] API key auth
- [x] API key + IP rate limiting
- [x] payload size and chain allowlist validation
- [x] deterministic message id and replay handling
- [x] contract replay checks and relayer authorization
- [x] CI for backend and contract tests
- [ ] External smart-contract audit
- [ ] Bug bounty program
