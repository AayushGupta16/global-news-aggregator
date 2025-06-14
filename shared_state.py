# shared_state.py

from typing import Dict, Any
from dotenv import load_dotenv
import os

# Load environment variables
dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path)
GEMINI_API_KEY = os.getenv('GOOGLE_GEMINI_API_KEY')

# This dictionary will store the status of all jobs.
# It's in a separate file to be safely imported by different modules.
jobs: Dict[str, Dict[str, Any]] = {}

