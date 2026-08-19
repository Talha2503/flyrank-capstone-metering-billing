Usage Metering & Billing Engine — Design Doc
FlyRank Backend Track Capstone

Stack: Python + FastAPI, PostgreSQL (Docker), Stripe (test mode)
1. Problem Statement
Every SaaS product needs to answer three questions for each customer: how much have they used, how much should they pay, and have they hit their plan limit? This service meters usage per tenant, enforces subscription quotas, calculates cost (including AI-token pricing rules), and stays in sync with Stripe subscription state via verified webhooks — all while guaranteeing that retries never cause double-counting or double-charging.
2. Data Model
tenants
•	id (PK, UUID)
•	name
•	created_at
plans
•	id (PK)
•	name (Free / Pro)
•	api_call_limit (int, monthly)
•	ai_token_limit (int, monthly)
•	price_cents (int)
subscriptions
•	id (PK)
•	tenant_id (FK → tenants)
•	plan_id (FK → plans)
•	stripe_customer_id
•	stripe_subscription_id
•	status (active / past_due / canceled)
•	current_period_start
•	current_period_end
•	updated_at
usage_events
•	id (PK)
•	tenant_id (FK → tenants)
•	type (api_call / ai_tokens)
•	quantity (int)
•	input_tokens / cached_input_tokens / output_tokens / reasoning_tokens (nullable, for ai_tokens type)
•	idempotency_key (unique per tenant)
•	created_at
processed_webhook_events (for Stripe dedup)
•	id (PK)
•	stripe_event_id (unique)
•	processed_at
3. Plans & Quotas
Plan	API calls / month	AI tokens / month	Price
Free	1,000	100,000	$0
Pro	50,000	5,000,000	$29/month
4. API Surface
POST /generate — the dummy billable endpoint
•	Headers: Idempotency-Key: <string>
•	Body: { "tenant_id": "...", "usage_type": "api_call" | "ai_tokens", "quantity": int, "token_breakdown": {...} } (token_breakdown only for ai_tokens)
•	Responses:
•	200 — usage recorded, { "usage_event_id": "...", "status": "recorded" }
•	200 (duplicate key) — same response as original, no new event created
•	429 — quota exceeded, { "error": "usage_quota_exceeded", "message": "..." }
•	402 — plan doesn't allow this action, { "error": "payment_required", "message": "..." }
GET /usage?tenant_id=...
•	Returns { "used": {...}, "limit": {...}, "cost_cents": int }
POST /checkout — creates a Stripe Checkout session for Free → Pro upgrade
POST /webhooks/stripe
•	Verifies signature (bad signature → 400)
•	Deduplicates by stripe_event_id
•	Handles: checkout.session.completed, customer.subscription.updated, customer.subscription.deleted
5. Idempotency Strategy
•	Client sends Idempotency-Key header with every /generate call.
•	Key is unique per tenant (composite uniqueness: tenant_id + idempotency_key).
•	On request: check if a usage_event already exists with that tenant_id + key.
•	If yes → return the stored result, do not insert a new row, do not re-check quota.
•	If no → proceed to quota check → insert usage_event → return result.
•	Enforced at the database level with a unique constraint (not just application logic) so concurrent retries can't race past it.
6. Layer Sketch
•	HTTP layer (FastAPI routers) — request validation, status codes, no business logic
•	Service layer (MeterService, QuotaService, CostService, StripeService) — all business rules live here
•	Data layer (SQLAlchemy models/repositories) — Postgres access only
Business logic never talks to the DB or Stripe directly — services depend on repository/client interfaces, so the DB (SQLite ↔ Postgres) or payment provider could be swapped without touching logic.
7. Non-Goal
This system does not implement proration, invoicing, or overage billing in the core build. A customer who reaches their quota is blocked (429/402) rather than allowed to overage-bill. These are explicitly out of scope and listed only as stretch goals.

