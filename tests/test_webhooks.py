import json
import time
import stripe
from app import stripe_config


def _sign_payload(payload_dict):
    """Helper: builds a valid Stripe webhook signature for a test payload,
    the same way the real Stripe servers would."""
    payload = json.dumps(payload_dict)
    timestamp = int(time.time())
    signed_payload = f"{timestamp}.{payload}"
    secret = stripe_config.STRIPE_WEBHOOK_SECRET

    signature = stripe.WebhookSignature._compute_signature(signed_payload, secret)
    header = f"t={timestamp},v1={signature}"
    return payload, header


def test_forged_webhook_signature_returns_400(client):
    """A webhook with an invalid/forged signature must be rejected with
    400 and nothing in the system should change."""
    fake_payload = json.dumps({"id": "evt_fake", "type": "checkout.session.completed", "data": {"object": {}}})
    fake_signature = "t=1234567890,v1=totally_fake_signature"

    response = client.post(
        "/webhooks/stripe",
        content=fake_payload,
        headers={"stripe-signature": fake_signature},
    )
    assert response.status_code == 400


def test_missing_signature_header_returns_400(client):
    """No stripe-signature header at all -> reject, don't process blindly."""
    response = client.post(
        "/webhooks/stripe",
        content=json.dumps({"id": "evt_no_sig", "type": "checkout.session.completed"}),
    )
    assert response.status_code == 400


def test_valid_signature_but_unrecognized_event_type_is_acknowledged(client):
    """A correctly-signed event we don't specifically handle should still
    return 200 (acknowledged), not error out."""
    payload_dict = {
        "id": "evt_test_unhandled_001",
        "type": "some.event.we.dont.handle",
        "data": {"object": {}},
    }
    payload, header = _sign_payload(payload_dict)

    response = client.post(
        "/webhooks/stripe",
        content=payload,
        headers={"stripe-signature": header},
    )
    assert response.status_code == 200


def test_duplicate_webhook_event_is_processed_only_once(client, db_session):
    """The same event ID delivered twice (a Stripe retry/replay) must be
    processed only once -- the second delivery is acknowledged but ignored."""
    payload_dict = {
        "id": "evt_test_duplicate_001",
        "type": "some.event.we.dont.handle",
        "data": {"object": {}},
    }
    payload, header = _sign_payload(payload_dict)

    first_response = client.post(
        "/webhooks/stripe", content=payload, headers={"stripe-signature": header}
    )
    assert first_response.status_code == 200
    assert first_response.json()["status"] == "processed"

    second_response = client.post(
        "/webhooks/stripe", content=payload, headers={"stripe-signature": header}
    )
    assert second_response.status_code == 200
    assert second_response.json()["status"] == "duplicate_ignored"

    # cleanup
    from app import models
    db_session.query(models.ProcessedWebhookEvent).filter_by(
        stripe_event_id="evt_test_duplicate_001"
    ).delete()
    db_session.commit()