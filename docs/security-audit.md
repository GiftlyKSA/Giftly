# Giftly Backend — Open Security Findings

> Last updated: 2026-04-24
> Scope: `src/` — all routers, middleware, utils, models, schemas

**No open findings.** All identified security issues have been resolved.

---

## Resolved (summary)

| Severity | Finding | Fix |
|---|---|---|
| CRITICAL | Paylink webhook trust without verification | Re-validate against live Paylink API + rate limit callbacks |
| HIGH | Non-constant-time OTP comparison | `secrets.compare_digest()` |
| HIGH | In-memory rate limits bypass in multi-worker | Redis INCR+EXPIRE with in-memory fallback for dev |
| HIGH | Admin Basic Auth over plain HTTP | Trust `X-Forwarded-Proto` from load balancer |
| HIGH | IDOR on invoice endpoints | `or_()` checks for customer + assigned courier |
| HIGH | No auth on `POST /invoices/` | Courier-only + order assignment check |
| MEDIUM | CORS wildcard in production | Startup guard raises RuntimeError |
| MEDIUM | `data: dict` on admin/wallet endpoints | Pydantic schemas with field constraints |
| MEDIUM | Order status free-form transitions | Linear state machine enforced |
| MEDIUM | Promocode apply endpoint unthrottled | Per-IP rate limit added |
| MEDIUM | No audit log for admin actions | `AuditLog` model + dashboard + write on all admin mutations |
| LOW | `is_verified` JWT claim stale in WebSocket | WebSocket fetches fresh user from DB |
| LOW | Duplicate invoice creation endpoints | Removed `POST /invoices/`, kept `/courier/create` |
| LOW | Dependency vulnerability scanning absent | `pip-audit` in CI via uv |
| LOW | `datetime.utcnow()` naive comparison | `datetime.now(timezone.utc)` throughout |
| LOW | User input not html.escaped | `html.escape()` on event titles, order descriptions, cancel reasons, chat |
