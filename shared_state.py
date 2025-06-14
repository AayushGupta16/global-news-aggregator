# shared_state.py

from typing import Dict, Any

# This dictionary will store the status of all jobs.
# It's in a separate file to be safely imported by different modules.
jobs: Dict[str, Dict[str, Any]] = {}

