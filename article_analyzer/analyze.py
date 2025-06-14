import json
import logging
import os
from typing import List, Optional
from models.models import ArticleAnalysisResult, ChinaPressRelease
from google import genai
from google.genai import types
from shared_state import GEMINI_API_KEY


client = genai.Client(api_key=GEMINI_API_KEY)

MODEL = "gemini-2.5-flash-preview-05-20" 
                                       


async def translate_to_english(article: ChinaPressRelease) -> str:
    """Translate article title and content to English using Gemini."""
    
    prompt = (
        "You are a professional translator. Translate the following document "
        "into natural, fluent English. Respond with only the translated text "
        "and no additional commentary.\n\n" + str(article)
    )
    # FIX: Use await with client.aio.models
    response = await client.aio.models.generate_content(contents=prompt, model=MODEL)
    if response.text is not None:
        return response.text.strip()
    else:
        logging.warning("Gemini did not return text for translation. Response: %s", response)
        if response.prompt_feedback:
            logging.warning("Translation prompt feedback: %s", response.prompt_feedback)
        # Fallback for translation if it fails
        return f"Translation failed for: {article.title}" # Return original or a placeholder


async def score_relevance(english_text: str) -> int:
    """Return Likert (1-7) relevance score for *english_text* using Gemini."""

    prompt = (
        "Rate the global relevance of the following government press-release "
        "on a 1-7 Likert scale (1 ⇒ not relevant at all, 7 ⇒ highly relevant). "
        "Respond with *only* the integer number (no explanation).\n\n" + english_text
    )

    # FIX: Use await with client.aio.models
    response = await client.aio.models.generate_content(
        contents=prompt,
        model=MODEL,
        config=types.GenerateContentConfig(temperature=0)
    )
    
    # Handle potential NoneType from .text
    if response.text is not None:
        # Extract first integer 1-7.
        for token in response.text.split():
            if token.strip().isdigit():
                val = int(token)
                if 1 <= val <= 7:
                    return val
        logging.info("Unable to parse relevance score from Gemini response: %s (Raw response: %s)", response.text, response)
    else:
        logging.warning("Gemini did not return text for relevance scoring. Response: %s", response)
        if response.prompt_feedback:
            logging.warning("Relevance prompt feedback: %s", response.prompt_feedback)
            
    return -1  # pessimistic fallback


async def generate_headline(english_text: str) -> str:
    """Generate a catchy two-sentence headline."""
    prompt = (
        "Create a catchy, journalist-style headline for the following article. "
        "The headline *must* be exactly two sentences.\n\n" + english_text
    )
    # FIX: Use await with client.aio.models and increase max_output_tokens
    response = await client.aio.models.generate_content(
        contents=prompt,
        model=MODEL,
        config=types.GenerateContentConfig(temperature=0.8) # Increased from 60
    )
    
    # Check if response.text is not None before stripping
    if response.text is not None:
        return response.text.strip()
    else:
        logging.warning("Gemini did not return text for headline generation. Response: %s", response)
        if response.prompt_feedback:
            logging.warning("Headline prompt feedback: %s", response.prompt_feedback)
        return "Headline could not be generated."


async def summarize_article(english_text: str) -> str:
    """Return two paragraphs: summary & takeaway."""
    prompt = (
        "Write a concise summary *and* key takeaway of the following article. "
        "Provide exactly two paragraphs in total, each 3-5 sentences. The first "
        "paragraph should summarise what the article says. The second "
        "paragraph should explain its broader relevance and implications.\n\n" + english_text
    )
    # FIX: Use await with client.aio.models and increase max_output_tokens
    response = await client.aio.models.generate_content(
        contents=prompt,
        model=MODEL,
        config=types.GenerateContentConfig(temperature=0.5) # Increased from 300
    )
    
    # Check if response.text is not None before stripping
    if response.text is not None:
        return response.text.strip()
    else:
        logging.warning("Gemini did not return text for summary generation. Response: %s", response)
        if response.prompt_feedback:
            logging.warning("Summary prompt feedback: %s", response.prompt_feedback)
        return "Summary and takeaway could not be generated."


async def tag_categories(english_text: str, max_tags: int = 5) -> List[str]:
    """Assign up to *max_tags* topical categories to *english_text*."""
    prompt = (
        f"Label the following article with up to {max_tags} topical categories. "
        "Return your answer as a JSON array of strings with no additional text.\n\n" + english_text
    )
    # FIX: Use await with client.aio.models and increase max_output_tokens
    response = await client.aio.models.generate_content(
        contents=prompt,
        model=MODEL,
        config=types.GenerateContentConfig(temperature=0.3) # Increased from 60
    )
    
    raw = None
    if response.text is not None:
        raw = response.text
    else:
        logging.warning("Gemini did not return text for category tagging. Response: %s", response)
        if response.prompt_feedback:
            logging.warning("Category tagging prompt feedback: %s", response.prompt_feedback)
        return [] # Return empty list if tagging fails

    try:
        tags = json.loads(raw)
        # Make sure we got a list[str]
        if isinstance(tags, list):
            return [str(t).strip() for t in tags][:max_tags]
    except json.JSONDecodeError:
        logging.warning("Could not parse categories JSON. Gemini output: %s", raw)
        # Fallback – try to split by commas / newlines if JSON parsing fails
        return [t.strip() for t in raw.replace("[", "").replace("]", "").split(",") if t.strip()][:max_tags]
    except Exception as e:
        logging.warning("An unexpected error occurred during category parsing: %s. Gemini output: %s", e, raw)
        return [] # Generic fallback for other exceptions


# ---------------------------------------------------------------------------
# Driver function
# ---------------------------------------------------------------------------

# FIX: Make analyze_article an async function
async def analyze_article(article: ChinaPressRelease, *, relevance_threshold: int = 5) -> ArticleAnalysisResult:
    """End-to-end pipeline described in the module docstring.

    Parameters
    ----------
    article_content:
        ChinaPressRelease object containing the article data.
    relevance_threshold:
        Minimum Likert relevance score necessary to proceed with full analysis.
    """

    logging.info("[Analyzer] Starting analysis …")

    # FIX: Await calls to async helper functions
    english_text = await translate_to_english(article)
    # If translation fails, english_text might be a placeholder, you might want to handle this more robustly
    if not english_text or "Translation failed" in english_text: 
        logging.error("Failed to translate article, skipping analysis.")
        raise ValueError("Article translation failed.")

    # FIX: Await calls to async helper functions
    relevance_score = await score_relevance(english_text)
    logging.info("[Analyzer] Relevance score: %s", relevance_score)

    if relevance_score < relevance_threshold:
        return None


    # FIX: Await calls to async helper functions
    headline = await generate_headline(english_text)
    # FIX: Await calls to async helper functions
    summary = await summarize_article(english_text)
    # FIX: Await calls to async helper functions
    # categories = await tag_categories(english_text)
    categories = ["china"]


    result = ArticleAnalysisResult(
        headline=headline,
        summary=summary,
        categories=categories,
        relevance_score=relevance_score,
    )

    logging.info("[Analyzer] Analysis finished.")
    return result