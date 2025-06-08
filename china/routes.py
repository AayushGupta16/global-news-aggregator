import uuid
import logging
from playwright.async_api import async_playwright
from fastapi import APIRouter, BackgroundTasks, HTTPException
from shared_state import jobs
from models.models import ScrapeJob
import time

router = APIRouter(
    prefix="/china",
    tags=["China"],
)

async def fetch_china_press_releases_browser(num_pages: int = 1) -> list | None:
    """
    Uses a real browser to bypass bot detection and get the full HTML content.
    """
    all_articles = []
    
    logging.info("[China Scraper] Starting Playwright...")
    start_time = time.time()
    
    async with async_playwright() as p:
        logging.info("[China Scraper] Playwright initialized, launching browser...")
        
        # Launch browser with optimized settings for Docker
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',  # Important for Docker
                '--disable-gpu',
                '--no-sandbox',  # Required for Docker
                '--disable-setuid-sandbox',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process'
            ]
        )
        
        logging.info(f"[China Scraper] Browser launched in {time.time() - start_time:.2f} seconds")
        
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='zh-CN',
        )
        
        logging.info("[China Scraper] Browser context created")
        
        # Add extra headers
        await context.set_extra_http_headers({
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        })
        
        page = await context.new_page()
        logging.info("[China Scraper] New page created")
        
        try:
            for i in range(1, num_pages + 1):
                page_start = time.time()
                logging.info(f"[China Scraper] Fetching page {i}...")
                
                # Construct the URL
                if i == 1:
                    list_url = "https://www.gov.cn/zhengce/zuixin.htm"
                else:
                    list_url = f"https://www.gov.cn/zhengce/zuixin_{i}.htm"
                
                logging.info(f"[China Scraper] Navigating to {list_url}")
                
                # Navigate with shorter timeout
                try:
                    await page.goto(list_url, wait_until="domcontentloaded", timeout=30000)
                    logging.info(f"[China Scraper] Page loaded in {time.time() - page_start:.2f} seconds")
                except Exception as e:
                    logging.error(f"[China Scraper] Failed to load page: {e}")
                    continue
                
                # Quick wait
                await page.wait_for_timeout(2000)
                
                # Debug: Log what we see on the page
                page_title = await page.title()
                logging.info(f"[China Scraper] Page title: {page_title}")
                
                # Check for content
                has_content = await page.locator("div.news_box").count() > 0
                logging.info(f"[China Scraper] Has news_box: {has_content}")
                
                if not has_content:
                    # Log the page structure for debugging
                    body_text = await page.evaluate("() => document.body.innerText.substring(0, 500)")
                    logging.warning(f"[China Scraper] Page body preview: {body_text}")
                
                # Extract articles
                articles = await page.evaluate("""
                    () => {
                        const articles = [];
                        const newsItems = document.querySelectorAll('div.news_box .list_2 ul > li');
                        
                        console.log('Found news items:', newsItems.length);
                        
                        newsItems.forEach(item => {
                            const link = item.querySelector('a');
                            const dateSpan = item.querySelector('span.date');
                            
                            if (link && dateSpan) {
                                const href = link.getAttribute('href');
                                const fullUrl = href.startsWith('http') 
                                    ? href 
                                    : new URL(href, window.location.href).href;
                                
                                articles.push({
                                    maintitle: link.textContent.trim(),
                                    pub_url: fullUrl,
                                    publish_date: dateSpan.textContent.trim()
                                });
                            }
                        });
                        
                        return articles;
                    }
                """)
                
                logging.info(f"[China Scraper] Found {len(articles)} articles on page {i}")
                
                # Now fetch the FWZH tags and content for each article
                for article in articles:
                    logging.info(f"[China Scraper] Fetching details for: {article['maintitle']}")
                    
                    await page.goto(article['pub_url'], wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(1000)
                    
                    # Extract FWZH tag and content
                    article_details = await page.evaluate("""
                        () => {
                            // Extract FWZH
                            let fwzh = null;
                            
                            // Method 1: Look for the specific table structure
                            const fwzhRow = Array.from(document.querySelectorAll('tr')).find(row => {
                                const firstCell = row.querySelector('td');
                                return firstCell && firstCell.textContent.includes('发文字号');
                            });
                            
                            if (fwzhRow) {
                                const cells = fwzhRow.querySelectorAll('td');
                                if (cells.length >= 2) {
                                    const fwzhText = cells[1].textContent.trim();
                                    // Don't return if it's just "索 引 号："
                                    if (fwzhText && !fwzhText.includes('索 引 号')) {
                                        fwzh = fwzhText;
                                    }
                                }
                            }
                            
                            // Method 2: Look in the mobile version structure
                            if (!fwzh) {
                                const mobileSection = document.querySelector('.pchide.abstract.mxxgkabstract');
                                if (mobileSection) {
                                    const h2Elements = mobileSection.querySelectorAll('h2');
                                    for (let i = 0; i < h2Elements.length; i++) {
                                        if (h2Elements[i].textContent.includes('发文字号')) {
                                            const nextP = h2Elements[i].nextElementSibling;
                                            if (nextP && nextP.tagName === 'P') {
                                                const fwzhText = nextP.textContent.trim();
                                                if (fwzhText && !fwzhText.includes('索 引 号')) {
                                                    fwzh = fwzhText;
                                                    break;
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                            
                            // Method 3: Look for the pattern in various structures
                            if (!fwzh) {
                                const allTds = document.querySelectorAll('td');
                                for (let td of allTds) {
                                    const text = td.textContent.trim();
                                    // Look for patterns like "国发〔2025〕X号"
                                    const fwzhPattern = /[^〔]+〔\\d{4}〕\\d+号/;
                                    const match = text.match(fwzhPattern);
                                    if (match) {
                                        fwzh = match[0];
                                        break;
                                    }
                                }
                            }
                            
                            // Method 4: Direct text search as fallback
                            if (!fwzh) {
                                const pageText = document.body.innerText;
                                const match = pageText.match(/发文字号[:：]\\s*([^\\n]+)/);
                                if (match && match[1]) {
                                    const fwzhCandidate = match[1].trim();
                                    const fwzhPattern = /[^〔\\s]+〔\\d{4}〕\\d+号/;
                                    const extracted = fwzhCandidate.match(fwzhPattern);
                                    if (extracted) {
                                        fwzh = extracted[0];
                                    } else {
                                        const firstSegment = fwzhCandidate.split(/\\s+/)[0];
                                        if (firstSegment && !firstSegment.includes('索 引 号')) {
                                            fwzh = firstSegment;
                                        }
                                    }
                                }
                            }
                            
                            // Additional method: Check for document info sections
                            if (!fwzh) {
                                const docInfoSections = document.querySelectorAll('.pages_content table, .bd1, .table2');
                                for (let section of docInfoSections) {
                                    const text = section.textContent;
                                    if (text.includes('发文字号')) {
                                        const fwzhPattern = /[^〔\\s]+〔\\d{4}〕\\d+号/;
                                        const match = text.match(fwzhPattern);
                                        if (match) {
                                            fwzh = match[0];
                                            break;
                                        }
                                    }
                                }
                            }
                            
                            // If it's a document from party organizations, it might not have FWZH
                            const title = document.querySelector('h1, .article-title, .pages-title');
                            if (!fwzh && title && (title.textContent.includes('中共中央') || title.textContent.includes('中办') || title.textContent.includes('国办'))) {
                                fwzh = null; // These often don't have document numbers
                            }
                            
                            // Extract content
                            let content = '';
                            
                            // Method 1: Look for main content area with id UCAP-CONTENT
                            const ucapContent = document.querySelector('#UCAP-CONTENT');
                            if (ucapContent) {
                                content = ucapContent.innerText.trim();
                            }
                            
                            // Method 2: Look for pages_content div
                            if (!content) {
                                const pagesContent = document.querySelector('.pages_content');
                                if (pagesContent) {
                                    // Try to find the actual article content, skipping metadata tables
                                    const articleContent = pagesContent.querySelector('.article, .TRS_Editor, .Custom_UnionStyle');
                                    if (articleContent) {
                                        content = articleContent.innerText.trim();
                                    } else {
                                        // Get all text but try to skip the metadata table
                                        const allParagraphs = pagesContent.querySelectorAll('p');
                                        const contentParts = [];
                                        for (let p of allParagraphs) {
                                            const text = p.innerText.trim();
                                            if (text && !text.includes('发文字号') && !text.includes('索 引 号')) {
                                                contentParts.push(text);
                                            }
                                        }
                                        content = contentParts.join('\\n\\n');
                                    }
                                }
                            }
                            
                            // Method 3: Look for article content in various possible containers
                            if (!content) {
                                const possibleContainers = [
                                    '.article-content',
                                    '.content-text',
                                    '.main-content',
                                    '.text-content',
                                    '.detail-content',
                                    '.view_content',
                                    '#UCAP-CONTENT-FORPRINT'
                                ];
                                
                                for (let selector of possibleContainers) {
                                    const container = document.querySelector(selector);
                                    if (container) {
                                        content = container.innerText.trim();
                                        break;
                                    }
                                }
                            }
                            
                            // Method 4: For documents with specific structure
                            if (!content) {
                                const mainTable = document.querySelector('.bd1');
                                if (mainTable) {
                                    // Skip the metadata table and look for content after it
                                    let contentElement = mainTable.nextElementSibling;
                                    while (contentElement) {
                                        if (contentElement.innerText && contentElement.innerText.trim()) {
                                            content = contentElement.innerText.trim();
                                            break;
                                        }
                                        contentElement = contentElement.nextElementSibling;
                                    }
                                }
                            }
                            
                            // Clean up content
                            if (content) {
                                // Remove excessive whitespace and clean up
                                content = content
                                    .replace(/\\s+/g, ' ')
                                    .replace(/\\n{3,}/g, '\\n\\n')
                                    .trim();
                                
                                // Limit content length to prevent massive documents
                                if (content.length > 10000) {
                                    content = content.substring(0, 10000) + '...';
                                }
                            }
                            
                            return {
                                fwzh: fwzh,
                                content: content
                            };
                        }
                    """)
                    
                    article['fwzh'] = article_details['fwzh']
                    article['content'] = article_details['content']
                    all_articles.append(article)
                    
                    # Respectful delay between requests
                    await page.wait_for_timeout(500)
                
        except Exception as e:
            logging.error(f"[China Scraper] Unexpected error: {e}", exc_info=True)
            return None
        finally:
            logging.info("[China Scraper] Closing browser...")
            await browser.close()
            logging.info(f"[China Scraper] Total time: {time.time() - start_time:.2f} seconds")
    
    return all_articles

async def run_scrape_and_update_status(job_id: str, num_pages: int):
    logging.info(f"[Job {job_id}] Background scrape started for {num_pages} pages.")
    try:
        data = await fetch_china_press_releases_browser(num_pages=num_pages)
        if data is not None:
            jobs[job_id]['status'] = 'completed'
            jobs[job_id]['result'] = {
                "country": "China",
                "method": "Browser Automation",
                "count": len(data),
                "data": data
            }
            logging.info(f"[Job {job_id}] Background scrape completed successfully.")
        else:
            jobs[job_id]['status'] = 'failed'
            jobs[job_id]['error_message'] = "Scraper finished but returned no data. The source website may have changed."
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