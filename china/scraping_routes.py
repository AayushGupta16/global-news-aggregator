import uuid
import logging
import time
import os
import asyncio
from typing import List, Optional
from browser_use import Agent, BrowserSession, Controller
from langchain_google_genai import ChatGoogleGenerativeAI
from fastapi import APIRouter, BackgroundTasks, HTTPException
from shared_state import jobs
from models.models import ScrapeJob, ChinaPressRelease, ArticleInfo, ArticleInfoList, ArticleDetails
from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path)
GOOGLE_API_KEY = os.getenv('GOOGLE_GEMINI_API_KEY')
MODEL = "gemini-2.5-flash-preview-05-20" 

router = APIRouter(
    prefix="/china",
    tags=["China"],
)

async def extract_details_with_agent(
    article_info: ArticleInfo,
    shared_browser_session: BrowserSession,
    llm: ChatGoogleGenerativeAI,
    semaphore: asyncio.Semaphore
) -> Optional[ChinaPressRelease]:
    async with semaphore:
        task = f"""
        You are a specialized data extractor. Your ONLY task is to visit the provided URL and extract two specific pieces of information.
        URL to visit: {article_info.pub_url}

        Instructions:
        1. Go to the URL.
        2. Visually scan the page to find the official document number, which is often labeled '发文字号'. Extract this as the `fwzh`. If it does not exist, set `fwzh` to null.
        3. Extract the full text content of the press release as `content`.
        4. Return ONLY these two fields in the required format.
        """
        controller = Controller(output_model=ArticleDetails)
        
        extractor_agent = Agent(
            task=task,
            llm=llm,
            controller=controller,
            browser_session=shared_browser_session,
            use_vision=True,
            max_failures=3,
        )
        
        try:
            logging.info(f"[Extractor Agent] Starting for: {article_info.maintitle}")
            history = await extractor_agent.run(max_steps=15)
            details_json = history.final_result()

            if not details_json:
                logging.warning(f"[Extractor Agent] Failed to extract details for {article_info.pub_url}")
                return None
            
            details = ArticleDetails.model_validate_json(details_json)

            return ChinaPressRelease(
                country="China",
                maintitle=article_info.maintitle,
                pub_url=article_info.pub_url,
                publish_date=article_info.publish_date,
                fwzh=details.fwzh,
                content=details.content
            )
        except Exception as e:
            logging.error(f"[Extractor Agent] Error processing {article_info.pub_url}: {e}", exc_info=True)
            return None


# --- Phase 1 & Orchestration ---
async def fetch_china_press_releases_agent(num_pages: int = 1) -> Optional[List[ChinaPressRelease]]:
    logging.info("[Orchestrator] Starting Phase 1: Main Agent URL Discovery...")
    start_time = time.time()

    if not GOOGLE_API_KEY:
        logging.error("[Orchestrator] GOOGLE_GEMINI_API_KEY not found in .env file.")
        raise ValueError("GOOGLE_GEMINI_API_KEY is not set.")

    # Initialize LLM once (Your update is kept)
    llm = ChatGoogleGenerativeAI(model=MODEL, google_api_key=GOOGLE_API_KEY)

    # Define the session but don't start it yet
    browser_session = BrowserSession(
        stealth=True, headless=True, channel='chromium', user_data_dir=None,
        keep_alive=True,
        args=['--disable-dev-shm-usage', '--disable-gpu', '--no-sandbox', '--disable-setuid-sandbox']
    )

    try:
        # --- FIX 1: Manually start the session before creating the first agent ---
        await browser_session.start()
        logging.info("[Orchestrator] Shared browser session started.")

        # --- Run Phase 1: Main "Discoverer" Agent ---
        discover_controller = Controller(output_model=ArticleInfoList)
        discover_task = f"""
        Your goal is to FIND recent Chinese government press releases. You have vision capabilities.
        IMPORTANT CONTEXT: The current date is June 14th, 2025. You are only interested in articles published on or after June 1, 2025.

        Follow these steps:
        1. Navigate through {num_pages} listing pages, starting with 'https://www.gov.cn/zhengce/zuixin.htm'.
        2. On each page, find all articles. For each one, check its publication date.
        3. IF an article is on or after June 1, 2025, collect its `maintitle`, full `pub_url`, and `publish_date`.
        4. IF an article is older, IGNORE it.
        **URL EXTRACTION RULE: To get the `pub_url`, you MUST inspect the `<a>` link element for each article and extract its `href` attribute. This is the only way to get the correct and unique URL. Do not invent a URL.
        Article URLs look like this: https://www.gov.cn/zhengce/202506/content_7027179.htm or https://www.gov.cn/zhengce/content/202506/content_7026294.htm
        Sometimes the url maybe be structured like ../202506/content_7027179.htm, in this case you need to add https://www.gov.cn/zhengce/ to the beginning of the url.
        5. CRITICAL: DO NOT navigate to the article detail pages. Your ONLY job is to create a list of articles to be processed later.
        6. After scanning all {num_pages} pages, return the complete list of found articles.





        """
        main_agent = Agent(
            task=discover_task, llm=llm, controller=discover_controller,
            browser_session=browser_session, use_vision=True, max_failures=5
        )

        history = await main_agent.run(max_steps=50 * num_pages)
        discovery_result_json = history.final_result()

        if not discovery_result_json:
            logging.warning("[Orchestrator] Phase 1 (Main Agent) failed to return any URLs.")
            return None

        articles_to_process = ArticleInfoList.model_validate_json(discovery_result_json).posts
        logging.info(f"[Orchestrator] Phase 1 complete. Found {len(articles_to_process)} recent articles.")
        if not articles_to_process:
            return []
        for article in articles_to_process:
            logging.info(f"[Orchestrator] url: {article.pub_url}")        

        return articles_to_process

        # --- Run Phase 2: Parallel "Extractor" Agents ---
        logging.info("[Orchestrator] Starting Phase 2: Spawning parallel Extractor Agents...")
        CONCURRENT_AGENTS = 5
        semaphore = asyncio.Semaphore(CONCURRENT_AGENTS)
        
        tasks = [
            extract_details_with_agent(article, browser_session, llm, semaphore)
            for article in articles_to_process
        ]
        
        scraped_results = await asyncio.gather(*tasks)
        
        final_articles = [res for res in scraped_results if res is not None]
        
        logging.info(f"[Orchestrator] Phase 2 complete. Successfully scraped details for {len(final_articles)} articles.")
        logging.info(f"Total time for all phases: {time.time() - start_time:.2f} seconds")
        
        return final_articles

    except Exception as e:
        logging.error(f"[Orchestrator] An unexpected error occurred: {e}", exc_info=True)
        return None
    finally:
        # --- FIX 2: Correctly close the session ---
        # The session object will always exist here. If start() failed, close() should handle it gracefully.
        # The incorrect 'is_running' check is removed.
        if browser_session:
            logging.info("[Orchestrator] Closing shared browser session.")
            await browser_session.close()


async def run_scrape_and_update_status(job_id: str, num_pages: int):
    logging.info(f"[Job {job_id}] Background scrape started using parallel AI agents.")
    try:
        data = await fetch_china_press_releases_agent(num_pages=num_pages)
        if data is not None:
            jobs[job_id]['status'] = 'completed'
            jobs[job_id]['result'] = {
                "country": "China",
                "method": "Parallel AI Agents (Browser Use)",
                "count": len(data),
                "data": [item.dict() for item in data]
            }
            logging.info(f"[Job {job_id}] Background scrape completed successfully.")
        else:
            jobs[job_id]['status'] = 'failed'
            jobs[job_id]['error_message'] = "Scraper finished but returned no data. The agent may have failed or no recent articles were found."
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