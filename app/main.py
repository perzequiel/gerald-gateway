from fastapi import FastAPI
from prometheus_client import make_asgi_app
from dotenv import load_dotenv
import os

load_dotenv()

from infrastructure.metrics.metrics import metrics_endpoint
from app.routers.v1 import router

# Import database models to ensure they're registered
from infrastructure.db.models import Base, DecisionModel, PlanModel, InstallmentModel, OutboundWebhookModel  # noqa: F401

app = FastAPI(title="gerald-gateway")

@app.get("/metrics")
async def metrics():
    return metrics_endpoint()

@app.get("/health")
async def health():
    return {"status": "ok", "message": "gerald-gateway is running"}

app.include_router(router)