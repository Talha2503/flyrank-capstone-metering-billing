from app import pricing_config


def _tokens_to_cents(token_count: int, price_cents_per_1k: int) -> int:
    """Converts a token count to a cost in integer cents, rounding down
    (never round up on a partial-thousand — that would overcharge)."""
    if token_count is None:
        return 0
    return (token_count * price_cents_per_1k) // 1000


class CostService:
    """Turns raw usage numbers into a cost in integer cents.

    Money is always stored/returned as integer cents, never floats,
    to avoid floating-point rounding errors in billing math.
    """

    def __init__(self, db=None):
        self.db = db

    def calculate_api_call_cost_cents(self, api_call_count: int) -> int:
        return _tokens_to_cents(api_call_count, pricing_config.API_CALL_PRICE_CENTS_PER_1K)

    def calculate_token_cost_cents(
        self,
        input_tokens: int = 0,
        cached_input_tokens: int = 0,
        output_tokens: int = 0,
        reasoning_tokens: int = 0,
    ) -> int:
        """
        Token categories are NOT simply summed and priced at one rate.
        Each category has its own rate:
          - fresh input tokens: standard input rate
          - cached input tokens: cheaper input rate
          - output tokens: output rate
          - reasoning tokens: billed at the OUTPUT rate (they are "hidden"
            output, not a separate free category)
        """
        cost = 0
        cost += _tokens_to_cents(input_tokens, pricing_config.INPUT_TOKEN_PRICE_CENTS_PER_1K)
        cost += _tokens_to_cents(
            cached_input_tokens, pricing_config.CACHED_INPUT_TOKEN_PRICE_CENTS_PER_1K
        )
        cost += _tokens_to_cents(output_tokens, pricing_config.OUTPUT_TOKEN_PRICE_CENTS_PER_1K)
        cost += _tokens_to_cents(reasoning_tokens, pricing_config.OUTPUT_TOKEN_PRICE_CENTS_PER_1K)
        return cost

    def calculate_total_cost_cents(self, usage_events: list) -> int:
        """Rolls up a list of UsageEvent rows into one total cost in cents."""
        total = 0
        for event in usage_events:
            if event.type == "api_call":
                total += self.calculate_api_call_cost_cents(event.quantity)
            elif event.type == "ai_tokens":
                total += self.calculate_token_cost_cents(
                    input_tokens=event.input_tokens or 0,
                    cached_input_tokens=event.cached_input_tokens or 0,
                    output_tokens=event.output_tokens or 0,
                    reasoning_tokens=event.reasoning_tokens or 0,
                )
        return total