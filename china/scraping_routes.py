import uuid
import logging
import time
import os
from typing import List, Optional
from browser_use import Agent, BrowserSession, Controller
from langchain_deepseek import ChatDeepSeek
from pydantic import SecretStr
from fastapi import APIRouter, BackgroundTasks, HTTPException
from shared_state import jobs
from models.models import ScrapeJob, ChinaPressRelease, ChinaPressReleaseList
from dotenv import load_dotenv
import os

# Load environment variables
dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path)
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')


router = APIRouter(
    prefix="/china",
    tags=["China"],
)

async def fetch_china_press_releases_agent(num_pages: int = 1) -> Optional[List[ChinaPressRelease]]:
    """
    Uses a browser-use AI agent to bypass bot detection and scrape content.
    """
    logging.info("[China Scraper] Initializing AI Agent with DeepSeek-V3...")
    start_time = time.time()

    # --- 1. Configure the LLM ---
    llm = ChatDeepSeek(base_url='https://api.deepseek.com/v1', model='deepseek-chat', api_key=SecretStr(DEEPSEEK_API_KEY))

    # --- 2. Configure the Browser Environment ---
    browser_session = BrowserSession(
        stealth=True,
        headless=True,
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        channel='chromium',
        user_data_dir=None,
        locale='zh-CN',
        viewport={'width': 1920, 'height': 1080},
        extra_http_headers={
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        },
        args=[
            '--disable-dev-shm-usage',  # Important for Docker
            '--disable-gpu',
            '--no-sandbox',             # Required for Docker
            '--disable-setuid-sandbox',
        ]
    )

    # --- 3. Define the Agent's Task and Output Format ---
    # The Controller defines the agent's capabilities and desired output format.
    controller = Controller(output_model=ChinaPressReleaseList)

    # This detailed task prompt replaces all the previous scraping logic.
    task = f"""
    Your goal is to scrape Chinese government press releases. You must process exactly {num_pages} page(s) of listings.

    Follow these steps precisely:
    1.  For each page number from 1 to {num_pages}, construct the correct URL. The URL for page 1 is 'https://www.gov.cn/zhengce/zuixin.htm'. For subsequent pages (e.g., page 2), the URL is 'https://www.gov.cn/zhengce/zuixin_2.htm'.
    2.  On each listing page, identify all the article links and their publication dates.
    3.  For each article you find, you MUST navigate to its detail page (`pub_url`).
    4.  On the article's detail page, extract the following information to populate the fields of the 'ChinaPressRelease' model:
        - maintitle: The main title of the article.
        - pub_url: The full URL of the article you are on.
        - publish_date: The publication date, which you should have from the listing page.
        - fwzh: The official document number. This is a critical field, often labeled with the text '发文字号' and may look like '国发〔2025〕X号'. Find this specific piece of information. If it does not exist on the page, this field must be null.
        - content: The full text content of the press release.
        - country: This field should always be "China".
    5.  Collect all the extracted 'ChinaPressRelease' objects into the 'posts' list. After processing all articles from all {num_pages} pages, complete the task by returning the final list.
    """

    # --- 4. Initialize and Run the Agent ---
    agent = Agent(
        task=task,
        llm=llm,
        controller=controller,
        browser_session=browser_session,
        use_vision=False,
    )

    try:
        logging.info(f"[China Scraper] AI Agent is starting the task. This may take a while...")
        history = await agent.run(max_steps=(100 * num_pages))
        logging.info(f"[China Scraper] AI Agent finished in {time.time() - start_time:.2f} seconds")

        final_result = history.final_result()

        if final_result:
            # The agent returns a JSON string, which we parse with our Pydantic model.
            parsed_data = ChinaPressReleaseList.model_validate_json(final_result)
            logging.info(f"[China Scraper] Successfully parsed {len(parsed_data.posts)} articles from the agent's output.")
            return parsed_data.posts
        else:
            logging.warning("[China Scraper] Agent finished but did not return a final result.")
            if history.errors():
                logging.error(f"Agent encountered errors: {history.errors()}")
            return None

    except Exception as e:
        logging.error(f"[China Scraper] An unexpected error occurred while running the agent: {e}", exc_info=True)
        return None
    finally:
        # The browser session is automatically closed by the agent unless keep_alive=True is set.
        logging.info("[China Scraper] Browser session has been closed.")


async def run_scrape_and_update_status(job_id: str, num_pages: int):
    """
    This background task function now calls our new agent-based scraper.
    """
    logging.info(f"[Job {job_id}] Background scrape started for {num_pages} pages using AI Agent.")
    try:
        # --- MODIFIED: Call the new agent function ---
        data = await fetch_china_press_releases_agent(num_pages=num_pages)
        # --- END MODIFICATION ---

        if data is not None:
            jobs[job_id]['status'] = 'completed'
            jobs[job_id]['result'] = {
                "country": "China",
                "method": "AI Agent (Browser Use)", # Updated method
                "count": len(data),
                "data": [item.dict() for item in data] # Convert Pydantic models to dicts for JSON serialization
            }
            logging.info(f"[Job {job_id}] Background scrape completed successfully.")
        else:
            jobs[job_id]['status'] = 'failed'
            jobs[job_id]['error_message'] = "Scraper finished but returned no data. The agent may have failed to complete the task or the website structure is too complex."
            logging.warning(f"[Job {job_id}] Background scrape failed: No data returned.")

    except Exception as e:
        logging.error(f"[Job {job_id}] An unexpected error occurred in the background task: {e}", exc_info=True)
        jobs[job_id]['status'] = 'failed'
        jobs[job_id]['error_message'] = str(e)


@router.post("/scrape", status_code=202, response_model=ScrapeJob)
async def trigger_china_scrape_job(background_tasks: BackgroundTasks, pages: int = 1):
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "pending", "result": None}

    background_tasks.add_task(run_scrape_and_update_status, job_id, pages)

    logging.info(f"[API] Job {job_id} created and scheduled for background execution.")

    return {
        "job_id": job_id,
        "status_url": f"/china/scrape/status/{job_id}"
    }