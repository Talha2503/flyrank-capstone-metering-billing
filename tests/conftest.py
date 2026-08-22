import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal, Base, engine
from app import models


@pytest.fixture(scope="function")
def client():
    return TestClient(app)


@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="function")
def test_tenant(db_session):
    """Creates a fresh tenant with an active Free subscription for each test,
    and cleans up afterward so tests don't interfere with each other."""
    free_plan = db_session.query(models.Plan).filter_by(name="Free").first()

    tenant = models.Tenant(name="Pytest Tenant")
    db_session.add(tenant)
    db_session.flush()

    subscription = models.Subscription(
        tenant_id=tenant.id,
        plan_id=free_plan.id,
        status="active",
    )
    db_session.add(subscription)
    db_session.commit()
    db_session.refresh(tenant)

    yield tenant

    # Cleanup: remove usage events, subscription, tenant
    db_session.query(models.UsageEvent).filter_by(tenant_id=tenant.id).delete()
    db_session.query(models.Subscription).filter_by(tenant_id=tenant.id).delete()
    db_session.query(models.Tenant).filter_by(id=tenant.id).delete()
    db_session.commit()