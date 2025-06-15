from pydantic import BaseModel, Field
from typing import Dict, Any, Literal, List, Optional



class ScrapeJob(BaseModel):
    job_id: str = Field(..., description="The unique ID for the scraping job.")
    status_url: str = Field(..., description="The URL to poll for job status.")

class JobStatus(BaseModel):
    status: Literal["pending", "completed", "failed"] = Field(..., description="The current status of the job.")
    result: Any = Field(None, description="The result of the job. Will be null if pending or failed.")
    error_message: str | None = Field(None, description="An error message if the job failed.")

class ChinaPressRelease(BaseModel):
    country: str = Field(..., description="The country where the press release was published.")
    maintitle: str = Field(..., description="The main title of the press release.")
    pub_url: str = Field(..., description="The URL of the press release on the government website.")
    publish_date: str = Field(..., description="The date the press release was published.")
    fwzh: str | None = Field(None, description="The FWZH (发文字号) of the press release.")
    content: str = Field(..., description="The content of the press release.")
    def __str__(self) -> str:
        """Return formatted text including title and content for translation."""
        return f"Title: {self.maintitle}\n\nContent: {self.content}"

    

class ArticleAnalysisResult(BaseModel):
    """Final analysis result returned by `analyze_article`."""

    headline: str = Field(..., description="Two-sentence catchy headline of the article.")
    summary: str = Field(..., description="Two paragraph summary & takeaway in English.")
    categories: List[str] = Field(..., description="List of tags that categorise the article.")
    relevance_score: int = Field(..., ge=1, le=7, description="Likert scale relevance score (1-7).")
    def __str__(self) -> str:
        """Return a formatted string representation."""
        return f"{self.headline}\n{self.summary}"
    
class ChinaPressReleaseList(ChinaPressRelease):
    """A wrapper to ask the agent for a list of press releases."""
    posts: List[ChinaPressRelease]


class ArticleInfo(ChinaPressRelease):
    """A simple model for the main agent to find URLs and basic info."""
    pass

class ArticleInfoList(ChinaPressRelease):
    """The output model for the main agent's URL discovery task."""
    posts: List[ArticleInfo]

class ArticleDetails(ChinaPressRelease):
    """The output model for the parallel extractor agents."""
    fwzh: Optional[str]
    content: Optional[str]