# scheduler.py

import logging
import os
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
        
        # if there are releases, post-process them with AI 
        articles = []
        for release in releases:
            article = await analyze_article(release)
            articles.append(article)

        # to string the articles and send an email
        body = "\n\n".join([f"{article.headline}\n{article.summary}\n{article.url}" for article in articles])
        
        # Email configuration from environment variables
        subject = "here's the latest China press release"
        sender = "aayugupta04@gmail.com"
        recipients = ["aayugupta04@gmail.com", "Carter.anderson0404@gmail.com"]
        password = os.getenv("EMAIL_PASSWORD")
        
        send_email(subject, body, sender, recipients, password)

    except Exception as e:
        logging.error(f"something fucked up in the scheduler: {e}", exc_info=True)


def setup_scheduler():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_china_scrape_job, 'cron', hour=2, minute=0, timezone='UTC')
    scheduler.add_job(run_china_scrape_job, 'date', run_date='now')
    logging.info("Scheduler initialized with Playwright job.")
    return scheduler