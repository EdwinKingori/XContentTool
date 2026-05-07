from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI 


# async def lifespan(app: Fastapi):
#     """
#     Startup and shutdown lifecycle
#     """

app = FastAPI(
    title ="X-Automation Tool",
    version = "1.0.0",
)



@app.get("/", tags=["System"])
async def root():
    return {
        "status": "Welcome to the X-Automation-Tool!",
        "service": "X-Automation-Tool",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

@app.get("/api/v1/health", tags=["System"])
async def health_status():
    return {
        "status": "Runnig OK!",
        "service": "X-Automation-Tool",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }