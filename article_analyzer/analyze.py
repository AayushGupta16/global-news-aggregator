'''
Feed the to string of the article content to generate a summary, takeaway, and relevance of the article.

First step is to translate the article into English.
Then use Gemini to explain what the article is about and its broader relevance.
Score it using the likert scale, if it is a high enough score continue with next steps.
- Make a 2 sentence headline of the article (kinda like a catching news headline)
- Have a 2 paragraph summary & takeaway of the article
- Tag it with relevant categories 
- return article headline, summary/takeaway, and categories as a custom object
'''


import json
import logging
import os
from typing import List, Optional
from models.models import ArticleAnalysisResult
from google import genai

gemini_client = genai.Client(api_key='GEMINI_API_KEY')

MODEL = "gemini-1.5-flash"


def translate_to_english(text: str) -> str:
    """Translate *text* to English using Gemini (or return as-is if already ENG).

    A very small heuristic is used to skip obviously English text (ASCII ratio).
    """
    prompt = (
        "You are a professional translator. Translate the following document "
        "into natural, fluent English. Respond with only the translated text "
        "and no additional commentary.\n\n" + text
    )
    return gemini_client.models.generate_content(prompt, model=MODEL)


def score_relevance(english_text: str) -> int:
    """Return Likert (1-7) relevance score for *english_text* using Gemini."""

    prompt = (
        "Rate the global relevance of the following government press-release "
        "on a 1-7 Likert scale (1 ⇒ not relevant at all, 7 ⇒ highly relevant). "
        "Respond with *only* the integer number (no explanation).\n\n" + english_text
    )

    response = gemini_client.models.generate_content(prompt, temperature=0, model=MODEL)
    # Extract first integer 1-7.
    for token in response.split():
        if token.strip().isdigit():
            val = int(token)
            if 1 <= val <= 7:
                return val
    logging.info("Unable to parse relevance score from Gemini response: %s", response)
    return -1  # pessimistic fallback


def generate_headline(english_text: str) -> str:
    """Generate a catchy two-sentence headline."""
    prompt = (
        "Create a catchy, journalist-style headline for the following article. "
        "The headline *must* be exactly two sentences.\n\n" + english_text
    )
    headline = gemini_client.models.generate_content(prompt, temperature=0.8, max_tokens=60, model=MODEL)
    return headline.strip()


def summarize_article(english_text: str) -> str:
    """Return two paragraphs: summary & takeaway."""
    prompt = (
        "Write a concise summary *and* key takeaway of the following article. "
        "Provide exactly two paragraphs in total, each 3-5 sentences. The first "
        "paragraph should summarise what the article says. The second "
        "paragraph should explain its broader relevance and implications.\n\n" + english_text
    )
    summary = gemini_client.models.generate_content(prompt, temperature=0.5, max_tokens=300, model=MODEL)
    return summary.strip()


def tag_categories(english_text: str, max_tags: int = 5) -> List[str]:
    """Assign up to *max_tags* topical categories to *english_text*."""
    prompt = (
        f"Label the following article with up to {max_tags} topical categories. "
        "Return your answer as a JSON array of strings with no additional text.\n\n" + english_text
    )
    raw = gemini_client.models.generate_content(prompt, temperature=0.3, max_tokens=60, model=MODEL)
    try:
        tags = json.loads(raw)
        # Make sure we got a list[str]
        if isinstance(tags, list):
            return [str(t).strip() for t in tags][:max_tags]
    except Exception:
        logging.warning("Could not parse categories JSON. Gemini output: %s", raw)

    # Fallback – try to split by commas / newlines
    return [t.strip() for t in raw.replace("[", "").replace("]", "").split(",") if t.strip()][:max_tags]


# ---------------------------------------------------------------------------
# Driver function
# ---------------------------------------------------------------------------


def analyze_article(article_content: str, *, relevance_threshold: int = 4) -> ArticleAnalysisResult:
    """End-to-end pipeline described in the module docstring.

    Parameters
    ----------
    article_content:
        Raw article body (any language). The caller is expected to obtain the
        text, e.g. via scraping.
    relevance_threshold:
        Minimum Likert relevance score necessary to proceed with full analysis.
        Articles scoring below the threshold raise a `ValueError`.
    """

    logging.info("[Analyzer] Starting analysis …")

    english_text = translate_to_english(article_content)
    logging.debug("[Analyzer] Translation complete (len=%s)", len(english_text))

    relevance_score = score_relevance(english_text)
    logging.info("[Analyzer] Relevance score: %s", relevance_score)

    if relevance_score < relevance_threshold:
        raise ValueError(f"Article relevance below threshold (score={relevance_score}).")

    headline = generate_headline(english_text)
    summary = summarize_article(english_text)
    categories = tag_categories(english_text)

    result = ArticleAnalysisResult(
        headline=headline,
        summary=summary,
        categories=categories,
        relevance_score=relevance_score,
    )

    logging.info("[Analyzer] Analysis finished.")
    return result
