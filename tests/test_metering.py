def test_duplicate_idempotency_key_does_not_double_count(client, test_tenant):
    """The heart of the capstone: same idempotency key = one usage event,
    no matter how many times the request is retried."""
    payload = {
        "tenant_id": str(test_tenant.id),
        "usage_type": "api_call",
        "quantity": 1,
    }
    headers = {"Idempotency-Key": "pytest-duplicate-key"}

    first_response = client.post("/generate", json=payload, headers=headers)
    assert first_response.status_code == 200
    first_event_id = first_response.json()["usage_event_id"]

    second_response = client.post("/generate", json=payload, headers=headers)
    assert second_response.status_code == 200
    second_event_id = second_response.json()["usage_event_id"]

    # Same event ID both times -> proves no duplicate was created
    assert first_event_id == second_event_id

    # Usage should reflect exactly ONE recorded call, not two
    usage_response = client.get(f"/usage?tenant_id={test_tenant.id}")
    assert usage_response.json()["used"]["api_call"] == 1


def test_request_at_exact_quota_boundary_is_allowed(client, test_tenant):
    """Free plan allows 1000 api_calls. A single request for exactly
    1000 should be allowed (boundary is inclusive)."""
    payload = {
        "tenant_id": str(test_tenant.id),
        "usage_type": "api_call",
        "quantity": 1000,
    }
    headers = {"Idempotency-Key": "pytest-boundary-exact"}

    response = client.post("/generate", json=payload, headers=headers)
    assert response.status_code == 200


def test_request_over_quota_boundary_is_rejected_with_429(client, test_tenant):
    """A request that would push usage OVER the limit must be rejected
    with 429 and a clear message."""
    payload = {
        "tenant_id": str(test_tenant.id),
        "usage_type": "api_call",
        "quantity": 1001,
    }
    headers = {"Idempotency-Key": "pytest-boundary-over"}

    response = client.post("/generate", json=payload, headers=headers)
    assert response.status_code == 429
    body = response.json()
    assert body["detail"]["error"] == "usage_quota_exceeded"


def test_no_subscription_returns_402(client, db_session):
    """A tenant with no active subscription should get 402, not 429 —
    these are semantically different failure modes."""
    from app import models
    tenant = models.Tenant(name="No Sub Tenant")
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    payload = {
        "tenant_id": str(tenant.id),
        "usage_type": "api_call",
        "quantity": 1,
    }
    headers = {"Idempotency-Key": "pytest-no-sub"}

    response = client.post("/generate", json=payload, headers=headers)
    assert response.status_code == 402

    # cleanup
    db_session.query(models.Tenant).filter_by(id=tenant.id).delete()
    db_session.commit()