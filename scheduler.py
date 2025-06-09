# scheduler.py

import logging
import os
from datetime import datetime
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from china.scraping_routes import fetch_china_press_releases_browser 
from article_analyzer.analyze import analyze_article
from emailing.email import send_email

# Load environment variables
load_dotenv()

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
        
        # Limit to max 10 releases
        releases_to_process = releases[:5]
        logging.info(f"Processing {len(releases_to_process)} releases (max 10)")
        
        # Modify your processing loop to keep both objects
        processed_items = []
        for release in releases_to_process:
            article = await analyze_article(release)
            processed_items.append((article, release))

        # Create email body with access to both
        body = "\n\n".join([
            f"{article.headline}\n{article.summary}\n{release.pub_url}" 
            for article, release in processed_items if article and release
        ])
        send_email(body)


    except Exception as e:
        logging.error(f"something fucked up in the scheduler: {e}", exc_info=True)


def setup_scheduler():
    scheduler = AsyncIOScheduler()
    # Regular scheduled job - runs daily at 2 AM UTC
    scheduler.add_job(run_china_scrape_job, 'cron', hour=2, minute=0, timezone='UTC')
    
    # Run immediately on startup using datetime.now()
    scheduler.add_job(run_china_scrape_job, 'date', run_date=datetime.now())
    
    logging.info("Scheduler initialized with Playwright job.")
    return scheduler