from fastapi import FastAPI
from app.routers import generate

app = FastAPI(title="Usage Metering & Billing Engine")

app.include_router(generate.router)


@app.get("/")
def root():
    return {"status": "ok", "service": "usage-metering-billing-engine"}