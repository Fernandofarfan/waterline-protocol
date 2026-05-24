# HCMessage v1 Specification

## Canonical fields
- `operation_id` (`uint256`)
- `criticality_profile` (`string`) one of: `medical|food|emergency|standard`
- `target_chains` (`string[]`) unique values from allowlist
- `payload` (`object`) canonicalized with sorted keys (`JSON`)

## Deterministic message_id
`message_id = sha256("{operation_id}|{criticality_profile}|{canonical_payload_json}")`

Where `canonical_payload_json` is serialized with sorted keys and UTF-8 encoding.

## Replay semantics
- If `message_id` already exists, operation is marked `replayed`.
- If `operation_id` exists with a different computed `message_id`, request MUST fail with `409`.

## State machine
Allowed transitions:
- `queued -> sent|failed`
- `sent -> acknowledged|failed`
- `acknowledged -> finalized|failed`
- `failed/finalized/replayed -> (none)`

## Validation vectors
1. Same `operation_id`, same payload => same `message_id`.
2. Same `operation_id`, different payload => conflict `409`.
3. Repeating exact request => `replayed`.
4. Invalid transition (`queued -> finalized`) => `409`.
