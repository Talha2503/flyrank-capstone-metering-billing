from app.services.cost_service import CostService


def test_api_call_cost_calculation():
    """1000 api_calls at 10 cents/1k -> 10 cents."""
    service = CostService()
    assert service.calculate_api_call_cost_cents(1000) == 10
    assert service.calculate_api_call_cost_cents(5000) == 50
    assert service.calculate_api_call_cost_cents(0) == 0


def test_api_call_cost_rounds_down_on_partial_thousand():
    """500 calls is half of 1000 -> half of 10 cents -> integer division
    rounds DOWN, never up (never overcharge on a fraction)."""
    service = CostService()
    assert service.calculate_api_call_cost_cents(500) == 5
    assert service.calculate_api_call_cost_cents(999) == 9  # rounds down, not up to 10


def test_input_token_cost():
    """1000 input tokens at 3 cents/1k -> 3 cents."""
    service = CostService()
    cost = service.calculate_token_cost_cents(input_tokens=1000)
    assert cost == 3


def test_cached_input_tokens_are_cheaper_than_fresh_input():
    """The core pricing rule: cached input tokens must cost LESS than
    the same quantity of fresh input tokens."""
    service = CostService()
    fresh_cost = service.calculate_token_cost_cents(input_tokens=1000)
    cached_cost = service.calculate_token_cost_cents(cached_input_tokens=1000)
    assert cached_cost < fresh_cost
    assert fresh_cost == 3
    assert cached_cost == 1


def test_reasoning_tokens_billed_at_output_rate_not_free():
    """Reasoning tokens are NOT a free/separate category -- they must
    cost the SAME as output tokens, not zero, not less."""
    service = CostService()
    output_cost = service.calculate_token_cost_cents(output_tokens=1000)
    reasoning_cost = service.calculate_token_cost_cents(reasoning_tokens=1000)
    assert reasoning_cost == output_cost
    assert reasoning_cost == 15  # matches OUTPUT_TOKEN_PRICE_CENTS_PER_1K


def test_token_categories_are_not_simply_summed_at_one_rate():
    """1000 input + 1000 cached + 1000 output must NOT all cost the same
    per-token rate -- each category is priced independently, then summed."""
    service = CostService()
    cost = service.calculate_token_cost_cents(
        input_tokens=1000, cached_input_tokens=1000, output_tokens=1000
    )
    # 3 (input) + 1 (cached) + 15 (output) = 19, not 1000*some_flat_rate
    assert cost == 19


def test_mixed_token_usage_full_breakdown():
    """A realistic mixed request: some fresh input, some cached input,
    some output, some reasoning -- all four categories priced correctly
    and summed."""
    service = CostService()
    cost = service.calculate_token_cost_cents(
        input_tokens=2000,          # 2 * 3  = 6
        cached_input_tokens=5000,   # 5 * 1  = 5
        output_tokens=1000,         # 1 * 15 = 15
        reasoning_tokens=500,       # 0.5 * 15 = 7 (rounds down)
    )
    assert cost == 6 + 5 + 15 + 7


def test_zero_usage_costs_zero():
    service = CostService()
    assert service.calculate_token_cost_cents() == 0
    assert service.calculate_api_call_cost_cents(0) == 0


def test_none_token_counts_treated_as_zero():
    """A usage event with some token fields left as None (not applicable
    to that event) should not crash and should cost 0 for that category."""
    service = CostService()
    cost = service.calculate_token_cost_cents(
        input_tokens=None, cached_input_tokens=1000, output_tokens=None, reasoning_tokens=None
    )
    assert cost == 1  # only the cached_input_tokens contributes