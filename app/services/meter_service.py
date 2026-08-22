from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app import models


class MeterService:
    def __init__(self, db: Session):
        self.db = db

    def record_usage(
        self,
        tenant_id,
        usage_type: str,
        quantity: int,
        idempotency_key: str,
        token_breakdown: dict | None = None,
    ):
        """
        Records a usage event. If the same tenant_id + idempotency_key
        was already used, returns the original event instead of creating
        a new one — guarantees exactly-once metering under retries.
        """
        # Check for an existing event with this idempotency key first
        existing = (
            self.db.query(models.UsageEvent)
            .filter_by(tenant_id=tenant_id, idempotency_key=idempotency_key)
            .first()
        )
        if existing:
            return existing, False  # False = not newly created (duplicate)

        token_breakdown = token_breakdown or {}

        event = models.UsageEvent(
            tenant_id=tenant_id,
            type=usage_type,
            quantity=quantity,
            input_tokens=token_breakdown.get("input_tokens"),
            cached_input_tokens=token_breakdown.get("cached_input_tokens"),
            output_tokens=token_breakdown.get("output_tokens"),
            reasoning_tokens=token_breakdown.get("reasoning_tokens"),
            idempotency_key=idempotency_key,
        )

        self.db.add(event)
        try:
            self.db.commit()
            self.db.refresh(event)
            return event, True  # True = newly created
        except IntegrityError:
            # Race condition: two concurrent requests with the same key.
            # The unique constraint caught it — roll back and return the
            # row that won the race.
            self.db.rollback()
            existing = (
                self.db.query(models.UsageEvent)
                .filter_by(tenant_id=tenant_id, idempotency_key=idempotency_key)
                .first()
            )
            return existing, False