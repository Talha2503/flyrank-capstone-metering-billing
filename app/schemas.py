from pydantic import BaseModel
from typing import Optional
from uuid import UUID


class TokenBreakdown(BaseModel):
    input_tokens: Optional[int] = None
    cached_input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    reasoning_tokens: Optional[int] = None


class GenerateRequest(BaseModel):
    tenant_id: UUID
    usage_type: str  # "api_call" or "ai_tokens"
    quantity: int
    token_breakdown: Optional[TokenBreakdown] = None


class GenerateResponse(BaseModel):
    usage_event_id: UUID
    status: str


class ErrorResponse(BaseModel):
    error: str
    message: str