from fastapi import FastAPI
from app.routers import generate, checkout, webhooks

app = FastAPI(title="Usage Metering & Billing Engine")

app.include_router(generate.router)
app.include_router(checkout.router)
app.include_router(webhooks.router)


@app.get("/")
def root():
    return {"status": "ok", "service": "usage-metering-billing-engine"}