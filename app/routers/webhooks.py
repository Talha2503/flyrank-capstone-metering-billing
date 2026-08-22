import stripe
from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, stripe_config

router = APIRouter()


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    # Step 1: Verify the signature. A forged or malformed webhook -> 400.
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, stripe_config.STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    # Step 2: Deduplicate. If we've already processed this event ID,
    # acknowledge it but do nothing further (a replayed event must not
    # be processed twice).
    already_processed = (
        db.query(models.ProcessedWebhookEvent)
        .filter_by(stripe_event_id=event["id"])
        .first()
    )
    if already_processed:
        return {"status": "duplicate_ignored"}

    # Step 3: Handle the event types we care about.
    event_type = event["type"]
    data_object = event["data"]["object"].to_dict()

    if event_type == "checkout.session.completed":
        _handle_checkout_completed(db, data_object)
    elif event_type == "customer.subscription.updated":
        _handle_subscription_updated(db, data_object)
    elif event_type == "customer.subscription.deleted":
        _handle_subscription_deleted(db, data_object)
    # Unrecognized event types are acknowledged but ignored -- this is
    # normal and expected (Stripe sends many event types we don't need).

    # Step 4: Record that we've processed this event, so a replay is
    # recognized and ignored next time.
    db.add(models.ProcessedWebhookEvent(stripe_event_id=event["id"]))
    db.commit()

    return {"status": "processed"}


def _handle_checkout_completed(db: Session, session_obj: dict):
    tenant_id = session_obj.get("metadata", {}).get("tenant_id") or session_obj.get(
        "client_reference_id"
    )
    if not tenant_id:
        return  # Nothing we can do without knowing the tenant

    pro_plan = db.query(models.Plan).filter_by(name="Pro").first()
    subscription = (
        db.query(models.Subscription).filter_by(tenant_id=tenant_id).first()
    )

    if subscription:
        subscription.plan_id = pro_plan.id
        subscription.status = "active"
        subscription.stripe_customer_id = session_obj.get("customer")
        subscription.stripe_subscription_id = session_obj.get("subscription")
    else:
        subscription = models.Subscription(
            tenant_id=tenant_id,
            plan_id=pro_plan.id,
            status="active",
            stripe_customer_id=session_obj.get("customer"),
            stripe_subscription_id=session_obj.get("subscription"),
        )
        db.add(subscription)

    db.commit()


def _handle_subscription_updated(db: Session, subscription_obj: dict):
    stripe_sub_id = subscription_obj.get("id")
    subscription = (
        db.query(models.Subscription)
        .filter_by(stripe_subscription_id=stripe_sub_id)
        .first()
    )
    if not subscription:
        return

    subscription.status = subscription_obj.get("status", subscription.status)
    db.commit()


def _handle_subscription_deleted(db: Session, subscription_obj: dict):
    stripe_sub_id = subscription_obj.get("id")
    subscription = (
        db.query(models.Subscription)
        .filter_by(stripe_subscription_id=stripe_sub_id)
        .first()
    )
    if not subscription:
        return

    free_plan = db.query(models.Plan).filter_by(name="Free").first()
    subscription.plan_id = free_plan.id
    subscription.status = "canceled"
    db.commit()