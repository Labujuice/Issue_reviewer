import os
import re
from dotenv import load_dotenv

# Load environmental variables from .env file
load_dotenv()

def get_clean_env(key: str, default: str = "") -> str:
    """Get environment variable, strip inline comments and surrounding quotes/spaces."""
    val = os.getenv(key, default)
    if not val:
        return default
        
    val = val.strip()
    # Remove inline comments (e.g., 'value # comment' -> 'value')
    # But preserve if it's quoted (e.g., '"value # comment"')
    if not (val.startswith('"') and val.endswith('"')) and not (val.startswith("'") and val.endswith("'")):
        # Split by first unquoted '#'
        val = val.split('#')[0].strip()
        
    # Strip surrounding quotes if present
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        val = val[1:-1].strip()
        
    return val

def get_clean_repo(key: str) -> str:
    """Get GITHUB_REPO, and automatically extract 'owner/repo' if a URL is provided."""
    val = get_clean_env(key, "")
    if not val:
        return ""
    
    # Remove protocol
    if "://" in val:
        val = val.split("://", 1)[1]
    
    # Remove domain (e.g., github.com/)
    if val.lower().startswith("github.com/"):
        val = val[len("github.com/"):]
        
    val = val.rstrip("/")
    parts = val.split("/")
    if len(parts) >= 2:
        # Extract the last two parts: owner and repo
        return f"{parts[-2]}/{parts[-1]}"
    return val

class Config:
    # GitHub Configuration
    GITHUB_API_URL = get_clean_env("GITHUB_API_URL", "https://api.github.com").rstrip("/")
    GITHUB_TOKEN = get_clean_env("GITHUB_TOKEN", "")
    GITHUB_REPO = get_clean_repo("GITHUB_REPO")

    # Gemini Configuration
    GEMINI_API_KEY = get_clean_env("GEMINI_API_KEY", "")
    GEMINI_MODEL = get_clean_env("GEMINI_MODEL", "gemini-2.5-flash")

    # Webhooks
    SLACK_WEBHOOK_URL = get_clean_env("SLACK_WEBHOOK_URL", "")
    DISCORD_WEBHOOK_URL = get_clean_env("DISCORD_WEBHOOK_URL", "")

    @classmethod
    def validate(cls):
        """Validate that all required configurations are present."""
        errors = []
        if not cls.GITHUB_REPO:
            errors.append("GITHUB_REPO is required in your environment/.env file (e.g., 'owner/repo').")
        if not cls.GEMINI_API_KEY:
            errors.append("GEMINI_API_KEY is required in your environment/.env file.")

        if errors:
            raise ValueError("Configuration Error:\n" + "\n".join(f"- {e}" for e in errors))
