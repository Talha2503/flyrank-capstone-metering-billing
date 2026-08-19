# Usage Metering & Billing Engine

**FlyRank Backend Track Capstone**
**Author:** Talha
**Stack:** Python + FastAPI, PostgreSQL (Docker), Stripe (test mode)

---

## 1. Problem Statement

Every SaaS product needs to answer three questions for each customer: how much have they used, how much should they pay, and have they hit their plan limit? This service meters usage per tenant, enforces subscription quotas, calculates cost (including AI-token pricing rules), and stays in sync with Stripe subscription state via verified webhooks — all while guaranteeing that retries never cause double-counting or double-charging.

---

## 2. Data Model

### `tenants`
| Field | Type |
|---|---|
| id | PK, UUID |
| name | string |
| created_at | timestamp |

### `plans`
| Field | Type |
|---|---|
| id | PK |
| name | Free / Pro |
| api_call_limit | int (monthly) |
| ai_token_limit | int (monthly) |
| price_cents | int |

### `subscriptions`
| Field | Type |
|---|---|
| id | PK |
| tenant_id | FK → tenants |
| plan_id | FK → plans |
| stripe_customer_id | string |
| stripe_subscription_id | string |
| status | active / past_due / canceled |
| current_period_start | timestamp |
| current_period_end | timestamp |
| updated_at | timestamp |

### `usage_events`
| Field | Type |
|---|---|
| id | PK |
| tenant_id | FK → tenants |
| type | api_call / ai_tokens |
| quantity | int |
| input_tokens | int, nullable |
| cached_input_tokens | int, nullable |
| output_tokens | int, nullable |
| reasoning_tokens | int, nullable |
| idempotency_key | unique per tenant |
| created_at | timestamp |

### `processed_webhook_events` (Stripe dedup)
| Field | Type |
|---|---|
| id | PK |
| stripe_event_id | unique |
| processed_at | timestamp |

---

## 3. Plans & Quotas

| Plan | API calls / month | AI tokens / month | Price |
|------|-------------------|--------------------|----|
| Free | 1,000 | 100,000 | $0 |
| Pro | 50,000 | 5,000,000 | $29/month |

---

## 4. API Surface

### `POST /generate` — the dummy billable endpoint

**Headers:** `Idempotency-Key: <string>`

**Body:**
```json
{
  "tenant_id": "...",
  "usage_type": "api_call | ai_tokens",
  "quantity": 0,
  "token_breakdown": {}
}
```
> `token_breakdown` only required for `ai_tokens`.

**Responses:**
| Code | Meaning | Body |
|---|---|---|
| 200 | usage recorded | `{ "usage_event_id": "...", "status": "recorded" }` |
| 200 | duplicate key | same response as original — no new event created |
| 429 | quota exceeded | `{ "error": "usage_quota_exceeded", "message": "..." }` |
| 402 | plan doesn't allow this action | `{ "error": "payment_required", "message": "..." }` |

### `GET /usage?tenant_id=...`
Returns:
```json
{ "used": {}, "limit": {}, "cost_cents": 0 }
```

### `POST /checkout`
Creates a Stripe Checkout session for Free → Pro upgrade.

### `POST /webhooks/stripe`
- Verifies signature (bad signature → `400`)
- Deduplicates by `stripe_event_id`
- Handles: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`

---

## 5. Idempotency Strategy

- Client sends `Idempotency-Key` header with every `/generate` call.
- Key is unique **per tenant** (composite uniqueness: `tenant_id` + `idempotency_key`).
- On request:
  - If a `usage_event` already exists with that `tenant_id` + key → return the stored result, do not insert a new row, do not re-check quota.
  - If not → proceed to quota check → insert `usage_event` → return result.
- Enforced at the **database level** with a unique constraint (not just application logic), so concurrent retries can't race past it.

---

## 6. Layer Sketch

- **HTTP layer** (FastAPI routers) — request validation, status codes, no business logic
- **Service layer** (`MeterService`, `QuotaService`, `CostService`, `StripeService`) — all business rules live here
- **Data layer** (SQLAlchemy models/repositories) — Postgres access only

Business logic never talks to the DB or Stripe directly — services depend on repository/client interfaces, so the DB (SQLite ↔ Postgres) or payment provider could be swapped without touching logic.

---

## 7. Non-Goal

This system does **not** implement proration, invoicing, or overage billing in the core build. A customer who reaches their quota is blocked (`429`/`402`) rather than allowed to overage-bill. These are explicitly out of scope and listed only as stretch goals.
