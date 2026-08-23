# Build Log — AI Usage

This capstone was built with AI assistance (Claude) for scaffolding, debugging, and
explaining concepts. This log tracks where AI helped, where it got things wrong,
and what I changed or decided myself.

## Where AI helped
- Scaffolding the SQLAlchemy models, FastAPI routers, and service layer structure
  based on the design doc I wrote in Phase 1.
- Explaining the idempotency + quota-check ordering tradeoff (check-then-record
  vs record-then-check) — I chose check-before-record to avoid writing usage
  events for requests that get rejected.
- Debugging environment issues: Python 3.14 wheel-availability problems with
  psycopg2-binary and pydantic-core, and a Windows PATH issue with the Stripe CLI.
- Writing the initial pytest suite structure and fixtures.

## Where AI was wrong / needed correction
- The first draft of the `/generate` endpoint recorded the usage event BEFORE
  checking quota, which meant an over-quota request would still get written to
  the database. I caught this against my own design doc and had it rewritten to
  check quota first.
- The first version of the Stripe webhook handler crashed with a 500 error
  because it tried to call `.get()` on a Stripe SDK object, which only supports
  `obj["key"]` access, not `.get()`. Fixed by converting to a plain dict with
  `.to_dict()` before working with the payload.
- A real Stripe test-mode secret key ended up in `.env.example` by mistake
  during editing — GitHub's push protection caught it before it reached the
  public repo. Fixed by rewriting the file with placeholders only and amending
  the commit before pushing.

## Decisions I made myself
- Pricing constants and their values (app/pricing_config.py) — pinned per the
  brief's requirement, values are illustrative.
- Free/Pro plan quota numbers (1,000/100k calls-tokens for Free; 50,000/5M for Pro).
- Monthly rollup based on calendar-month start, documented as a stated assumption.
- Chose to check-quota-before-recording rather than record-then-rollback, for a
  cleaner "nothing written on rejection" guarantee.