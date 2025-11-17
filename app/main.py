from fastapi import FastAPI
from prometheus_client import make_asgi_app
from infrastructure.metrics.metrics import metrics_endpoint
from app.routers.v1 import router
app = FastAPI(title="gerald-gateway")

@app.get("/metrics")
async def metrics():
    return metrics_endpoint()

@app.get("/health")
async def health():
    return {"status": "ok", "message": "gerald-gateway is running"}

app.include_router(router)