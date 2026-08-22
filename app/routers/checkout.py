import stripe
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from uuid import UUID
from app.database import get_db
from app import models, stripe_config

router = APIRouter()


class CheckoutRequest(BaseModel):
    tenant_id: UUID


@router.post("/checkout")
def create_checkout_session(payload: CheckoutRequest, db: Session = Depends(get_db)):
    tenant = db.query(models.Tenant).filter_by(id=payload.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    pro_plan = db.query(models.Plan).filter_by(name="Pro").first()
    if not pro_plan:
        raise HTTPException(status_code=500, detail="Pro plan not seeded")

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {"name": "Pro Plan"},
                        "unit_amount": pro_plan.price_cents,
                        "recurring": {"interval": "month"},
                    },
                    "quantity": 1,
                }
            ],
            success_url="http://127.0.0.1:8000/checkout/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url="http://127.0.0.1:8000/checkout/cancel",
            client_reference_id=str(tenant.id),
            metadata={"tenant_id": str(tenant.id)},
        )
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=502, detail=f"Stripe error: {str(e)}")

    return {"checkout_url": session.url}