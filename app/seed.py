from app.database import Base, engine, SessionLocal
from app import models

def init_db():
    Base.metadata.create_all(bind=engine)
    print("Tables created.")

def seed_plans():
    db = SessionLocal()
    try:
        existing = db.query(models.Plan).count()
        if existing > 0:
            print("Plans already seeded, skipping.")
            return

        free_plan = models.Plan(
            name="Free",
            api_call_limit=1000,
            ai_token_limit=100000,
            price_cents=0,
        )
        pro_plan = models.Plan(
            name="Pro",
            api_call_limit=50000,
            ai_token_limit=5000000,
            price_cents=2900,
        )
        db.add_all([free_plan, pro_plan])
        db.commit()
        print("Free and Pro plans seeded.")
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
    seed_plans()