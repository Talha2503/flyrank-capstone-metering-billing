from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from app import models


class QuotaExceeded(Exception):
    """Raised when usage would exceed the plan's quota (-> 429)."""
    pass


class PaymentRequired(Exception):
    """Raised when the tenant has no active plan/subscription (-> 402)."""
    pass


class QuotaService:
    def __init__(self, db: Session):
        self.db = db

    def _current_period_start(self):
        # Simple monthly rollup: start of the current calendar month.
        now = datetime.utcnow()
        return datetime(now.year, now.month, 1)

    def get_tenant_plan(self, tenant_id):
        subscription = (
            self.db.query(models.Subscription)
            .filter_by(tenant_id=tenant_id, status="active")
            .first()
        )
        if not subscription:
            raise PaymentRequired("Tenant has no active subscription.")
        return subscription.plan

    def get_usage_totals(self, tenant_id):
        period_start = self._current_period_start()

        api_calls = (
            self.db.query(func.coalesce(func.sum(models.UsageEvent.quantity), 0))
            .filter(
                models.UsageEvent.tenant_id == tenant_id,
                models.UsageEvent.type == "api_call",
                models.UsageEvent.created_at >= period_start,
            )
            .scalar()
        )

        ai_tokens = (
            self.db.query(func.coalesce(func.sum(models.UsageEvent.quantity), 0))
            .filter(
                models.UsageEvent.tenant_id == tenant_id,
                models.UsageEvent.type == "ai_tokens",
                models.UsageEvent.created_at >= period_start,
            )
            .scalar()
        )

        return {"api_call": api_calls, "ai_tokens": ai_tokens}

    def check_quota(self, tenant_id, usage_type: str, quantity: int):
        """
        Raises PaymentRequired if the tenant has no active plan.
        Raises QuotaExceeded if this request would push usage over the limit.
        At-limit boundary rule: a request that lands exactly ON the limit
        is allowed; the request that would go OVER it is rejected.
        """
        plan = self.get_tenant_plan(tenant_id)
        totals = self.get_usage_totals(tenant_id)

        limit = plan.api_call_limit if usage_type == "api_call" else plan.ai_token_limit
        current_usage = totals[usage_type]

        if current_usage + quantity > limit:
            raise QuotaExceeded(
                f"Usage quota exceeded for '{usage_type}': "
                f"{current_usage}/{limit} used, requested {quantity} more."
            )

        return {"used": current_usage, "limit": limit}