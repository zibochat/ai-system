# Minimal config for Gemini
# You can set these directly here for testing, or better via env vars.
import os
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

# TODO: paste your Gemini API key here for local testing, or export GEMINI_API_KEY
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Example model for Gemini 2.5 (adjust to your access level):
#   - "gemini-2.5-flash"
#   - "gemini-2.5-pro"
# We'll normalize to the required "models/..." path automatically.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
