
import os
from pathlib import Path

from dotenv import load_dotenv

# Find the main project folder
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from the project's .env file
ENV_FILE = BASE_DIR / ".env"
load_dotenv(ENV_FILE)

# Gemini API configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

# Check whether Gemini is configured
LLM_AVAILABLE = bool(GEMINI_API_KEY)

# Important project paths
DATA_DIR = BASE_DIR / "data"
KNOWLEDGE_BASE_DIR = DATA_DIR / "knowledge_base"
DATABASE_PATH = DATA_DIR / "busbuddy.db"


def get_app_status():
    """Return the current application configuration status."""
    return {
        "project_dir": str(BASE_DIR),
        "gemini_available": LLM_AVAILABLE,
        "database_path": str(DATABASE_PATH),
    }

