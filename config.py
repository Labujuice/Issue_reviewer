import os
import re
from dotenv import load_dotenv

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
    # Repository Type (github, gitlab)
    REPO_PROVIDER = "github"

    # GitHub Configuration
    GITHUB_API_URL = "https://api.github.com"
    GITHUB_TOKEN = ""
    GITHUB_REPO = ""

    # GitLab Configuration
    GITLAB_URL = "https://gitlab.com"
    GITLAB_PRIVATE_TOKEN = ""
    GITLAB_PROJECT_ID = ""

    # Gemini Configuration
    GEMINI_API_KEY = ""
    GEMINI_MODEL = "gemini-2.5-flash"

    # Webhooks
    SLACK_WEBHOOK_URL = ""
    DISCORD_WEBHOOK_URL = ""

    # Output Configuration
    OUTPUT_FILE = "report.md"

    @classmethod
    def load(cls, env_path: str = None):
        """Load environmental variables dynamically from a specific .env file path."""
        # Load environment variables, overriding existing ones if loaded from a path
        if env_path:
            load_dotenv(dotenv_path=env_path, override=True)
        else:
            load_dotenv()

        cls.REPO_PROVIDER = get_clean_env("REPO_PROVIDER", "github").lower()

        # GitHub
        cls.GITHUB_API_URL = get_clean_env("GITHUB_API_URL", "https://api.github.com").rstrip("/")
        cls.GITHUB_TOKEN = get_clean_env("GITHUB_TOKEN", "")
        cls.GITHUB_REPO = get_clean_repo("GITHUB_REPO")

        # GitLab
        cls.GITLAB_URL = get_clean_env("GITLAB_URL", "https://gitlab.com").rstrip("/")
        cls.GITLAB_PRIVATE_TOKEN = get_clean_env("GITLAB_PRIVATE_TOKEN", "")
        cls.GITLAB_PROJECT_ID = get_clean_env("GITLAB_PROJECT_ID", "")

        # Gemini
        cls.GEMINI_API_KEY = get_clean_env("GEMINI_API_KEY", "")
        cls.GEMINI_MODEL = get_clean_env("GEMINI_MODEL", "gemini-2.5-flash")

        # Webhooks
        cls.SLACK_WEBHOOK_URL = get_clean_env("SLACK_WEBHOOK_URL", "")
        cls.DISCORD_WEBHOOK_URL = get_clean_env("DISCORD_WEBHOOK_URL", "")

        # Output File
        cls.OUTPUT_FILE = get_clean_env("OUTPUT_FILE", "report.md")

    @classmethod
    def validate(cls):
        """Validate that all required configurations for the active provider are present."""
        errors = []
        if cls.REPO_PROVIDER == "github":
            if not cls.GITHUB_REPO:
                errors.append("GITHUB_REPO is required in your environment/.env file (e.g., 'owner/repo').")
        elif cls.REPO_PROVIDER == "gitlab":
            if not cls.GITLAB_PROJECT_ID:
                errors.append("GITLAB_PROJECT_ID is required in your environment/.env file.")
        else:
            errors.append(f"Unsupported REPO_PROVIDER: {cls.REPO_PROVIDER}. Must be 'github' or 'gitlab'.")

        if not cls.GEMINI_API_KEY:
            errors.append("GEMINI_API_KEY is required in your environment/.env file.")

        if errors:
            raise ValueError("Configuration Error:\n" + "\n".join(f"- {e}" for e in errors))
