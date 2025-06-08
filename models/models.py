from pydantic import BaseModel, Field
from typing import Dict, Any, Literal

class ScrapeJob(BaseModel):
    job_id: str = Field(..., description="The unique ID for the scraping job.")
    status_url: str = Field(..., description="The URL to poll for job status.")

class JobStatus(BaseModel):
    status: Literal["pending", "completed", "failed"] = Field(..., description="The current status of the job.")
    result: Any = Field(None, description="The result of the job. Will be null if pending or failed.")
    error_message: str | None = Field(None, description="An error message if the job failed.")