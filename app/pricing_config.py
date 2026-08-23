# Pricing is expressed in cents per 1,000 tokens/calls, pinned here so
# tests can assert against known values. These are illustrative rates,
# not tied to any real provider's current pricing.

API_CALL_PRICE_CENTS_PER_1K = 10          # $0.10 per 1,000 API calls

# AI token pricing: cached input is cheaper than fresh input.
# Reasoning tokens are billed at the OUTPUT rate, not a separate category.
INPUT_TOKEN_PRICE_CENTS_PER_1K = 3        # $0.03 / 1k input tokens
CACHED_INPUT_TOKEN_PRICE_CENTS_PER_1K = 1  # $0.01 / 1k cached input tokens (cheaper)
OUTPUT_TOKEN_PRICE_CENTS_PER_1K = 15       # $0.15 / 1k output tokens
# Reasoning tokens intentionally reuse OUTPUT_TOKEN_PRICE_CENTS_PER_1K —
# there is no separate reasoning price constant. See CostService.