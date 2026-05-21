# MAX Support Desk Threat Model

Дата: 2026-05-21

## Scope

MVP web support desk:

- Django Admin + Unfold manager shell.
- Chatscope UI inside admin page.
- MAX webhook ingest.
- Staff JSON API.
- Outbound worker to MAX.
- Local media storage.
- External MySQL in production.

Out of scope for MVP:

- AI auto replies.
- Omnichannel adapters.
- Advanced malware scanning.
- Fine-grained departments/queues.

## Assets

- `MAX_BOT_TOKEN`.
- `MAX_WEBHOOK_SECRET`.
- Django session cookies.
- Manager accounts.
- MAX contacts and conversation history.
- Raw webhook payloads.
- Uploaded files.
- Audit records and delivery diagnostics.

## Trust Boundaries

- Internet -> `POST /webhooks/max/`.
- Manager browser -> Django session-authenticated admin/API.
- Django app -> external MySQL.
- Django worker -> MAX Platform API.
- Django app -> local media storage.
- WebSocket clients -> Channels staff-only consumer.

## Threats And Mitigations

- Forged MAX webhook:
  - Mitigation: `X-Max-Bot-Api-Secret` checked with constant-time comparison.

- Duplicate webhook delivery:
  - Mitigation: `RawUpdate.dedupe_key` unique; duplicate returns `200` without duplicate message.

- Message loss before socket/MAX side effects:
  - Mitigation: DB-first flow; socket/MAX events happen after commit.

- Unauthorized manager/API access:
  - Mitigation: Django session auth; staff checks on admin, chat page, JSON API, downloads, WebSocket.

- File leakage:
  - Mitigation: attachments served through protected API endpoint, not direct public media URLs.

- Token/secret leakage in logs:
  - Mitigation: sanitized structured logs; no tokens, cookies, session IDs, full raw payload dumps, or file contents in logs.

- Untraceable manager actions:
  - Mitigation: `ManagerActionLog` for send, retry, assignment, close, upload, download, CSV export.

- Outbound delivery debugging gaps:
  - Mitigation: `DeliveryAttempt` per worker attempt.

- Long-lived audit/service logs:
  - Mitigation: `cleanup_support_logs --days 7`.

## Residual Risks

- MVP does not scan uploaded files for malware.
- MVP uses a simple worker; multi-worker row locking can be added later.
- In-memory Channels layer is acceptable for local MVP only; production should use Redis if multiple processes are used.
- MAX payload shape should be validated against real production samples before public launch.
