import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import urljoin
import logging
import os


def scrape_china_press_releases() -> List[Dict[str, str]]:
    """
    Scrape Chinese government press releases using simple HTTP requests.
    Returns a list of articles with title, url, and date.
    """
    url = "https://www.gov.cn/zhengce/zuixin/home.htm"

    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Sec-Ch-Ua": '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"macOS"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        response.encoding = "utf-8"

        soup = BeautifulSoup(response.text, "html.parser")

        # Find all anchor tags
        links = soup.find_all(
            "a", href=lambda x: x and "content" in x and "home" not in x
        )

        articles = []
        for link in links:
            href = link["href"]

            # Filter links that contain "content" and don't contain "home"
            if "content" in href and "home" not in href:
                response.encoding = (
                    response.apparent_encoding or "utf-8"
                )  # Set response encoding to UTF-8
                title = link.get_text(strip=True)

                # Build full URL
                full_url = urljoin(response.url.split("?")[0], href)

                # Try to extract date from parent element
                date_str = None
                try:
                    parent = link.parent
                    if parent:
                        # Look for span with class="date" in the same parent
                        date_span = parent.find("span", class_="date")
                        if date_span:
                            date_str = date_span.get_text(strip=True)
                except Exception as e:
                    logging.debug(f"Error extracting date for {title}: {e}")

                if title:  # Only add if we have a title
                    articles.append(
                        {"title": title, "url": full_url, "date": date_str or "Unknown"}
                    )

        logging.info(f"Found {len(articles)} articles")
        return articles

    except requests.RequestException as e:
        logging.error(f"Error fetching data: {e}")
        return []
    except Exception as e:
        logging.error(f"Error parsing data: {e}")
        return []


if __name__ == "__main__":
    articles = scrape_china_press_releases()
    # dump to json
    with open("articles.json", "w") as f:
        json.dump(articles, f)

    for article in articles[:10]:  # Print first 10
        print(f"Title: {article['title']}")
        print(f"URL: {article['url']}")
        print(f"Date: {article['date']}")
        print("-" * 50)

    os.remove("articles.json")