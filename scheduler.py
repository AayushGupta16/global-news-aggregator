# scheduler.py

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from china.scraping_routes import fetch_china_press_releases_browser # Import the correct function

# The job must be async again
async def run_china_scrape_job():
    """
    A wrapper job for the scheduler to call the async Playwright scraper.
    """
    logging.info("[Scheduler] Starting scheduled Playwright job for China...")
    try:
        # gets the press releases
        releases = await fetch_china_press_releases_browser()

        # if no releases were found skip
        if not releases:
            logging.info("no press releases for today.")
            return
        
        # if there are releases, post-process them with AI 



    except Exception as e:
        logging.error(f"something fucked up in the scheduler: {e}", exc_info=True)


def setup_scheduler():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_china_scrape_job, 'cron', hour=2, minute=0, timezone='UTC')
    logging.info("Scheduler initialized with Playwright job.")
    return scheduler