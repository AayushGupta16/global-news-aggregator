# main.py

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from scheduler import setup_scheduler

# Import the shared jobs dictionary
from shared_state import jobs

# Import the router from our China module
from china.scraping_routes import router as china_router

# --- Centralized Logging Configuration ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# The scheduler instance
scheduler = setup_scheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("Application starting up...")
    scheduler.start()
    yield
    logging.info("Application shutting down...")
    scheduler.shutdown()

# --- FastAPI App Initialization ---
app = FastAPI(
    title="Multi-Country Press Release Monitor",
    description="A service to automatically scrape press releases from various government websites.",
    version="1.1.0", # Version bump!
    # lifespan=lifespan
)

# --- NEW: Job Status Endpoint ---
@app.get("/status/{job_id}", tags=["Jobs"])
async def get_status(job_id: str):
    """
    Check the status of a background scraping job.
    """
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

# --- Root Endpoint ---
@app.get("/", tags=["General"])
async def read_root():
    return {"message": "Welcome! See /docs for available endpoints."}

# --- Include Routers from Modules ---
app.include_router(china_router)