# scheduler.py

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from china.routes import fetch_china_press_releases_browser # Import the correct function

# The job must be async again
async def run_china_scrape_job():
    """
    A wrapper job for the scheduler to call the async Playwright scraper.
    """
    logging.info("[Scheduler] Starting scheduled Playwright job for China...")
    try:
        # Call the async function with await
        releases = await fetch_china_press_releases_browser()

        if releases:
            logging.info(f"[Scheduler] Job successful. Found {len(releases)} releases for China via Playwright.")
            # Post-processing would go here
        else:
            logging.warning("[Scheduler] Playwright job for China ran but found no data.")

    except Exception as e:
        logging.error(f"[Scheduler] An error occurred during the scheduled China scrape: {e}", exc_info=True)


def setup_scheduler():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_china_scrape_job, 'cron', hour=2, minute=0, timezone='UTC')
    logging.info("Scheduler initialized with Playwright job.")
    return scheduler