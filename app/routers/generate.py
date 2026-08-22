from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import GenerateRequest, GenerateResponse
from app.services.meter_service import MeterService
from app.services.quota_service import QuotaService, QuotaExceeded, PaymentRequired
from app import models

router = APIRouter()


@router.post("/generate", response_model=GenerateResponse)
def generate(
    payload: GenerateRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    db: Session = Depends(get_db),
):
    meter_service = MeterService(db)
    quota_service = QuotaService(db)

    # Step 1: Retry check FIRST. A duplicate key means nothing new
    # happened — return the original result, no quota re-check, no
    # new row written.
    existing_event = (
        db.query(models.UsageEvent)
        .filter_by(tenant_id=payload.tenant_id, idempotency_key=idempotency_key)
        .first()
    )
    if existing_event:
        return GenerateResponse(usage_event_id=existing_event.id, status="recorded")

    # Step 2: New request — check quota BEFORE recording anything.
    try:
        quota_service.check_quota(
            tenant_id=payload.tenant_id,
            usage_type=payload.usage_type,
            quantity=payload.quantity,
        )
    except PaymentRequired as e:
        raise HTTPException(status_code=402, detail={"error": "payment_required", "message": str(e)})
    except QuotaExceeded as e:
        raise HTTPException(status_code=429, detail={"error": "usage_quota_exceeded", "message": str(e)})

    # Step 3: Quota check passed — record the usage event.
    event, _ = meter_service.record_usage(
        tenant_id=payload.tenant_id,
        usage_type=payload.usage_type,
        quantity=payload.quantity,
        idempotency_key=idempotency_key,
        token_breakdown=payload.token_breakdown.dict() if payload.token_breakdown else None,
    )

    return GenerateResponse(usage_event_id=event.id, status="recorded")

@router.get("/usage")
def get_usage(tenant_id: str, db: Session = Depends(get_db)):
    from uuid import UUID
    quota_service = QuotaService(db)

    tenant_uuid = UUID(tenant_id)
    plan = quota_service.get_tenant_plan(tenant_uuid)
    totals = quota_service.get_usage_totals(tenant_uuid)

    return {
        "used": totals,
        "limit": {
            "api_call": plan.api_call_limit,
            "ai_tokens": plan.ai_token_limit,
        },
    }