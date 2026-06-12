import requests
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any

class GitHubFetcher:
    def __init__(self, repo: str, token: str = None, api_url: str = "https://api.github.com"):
        """
        Initialize GitHub fetcher.
        repo: owner/repo format (e.g., 'google/jax')
        token: GitHub Personal Access Token (PAT)
        api_url: API URL, defaults to public GitHub API
        """
        self.repo = repo
        self.token = token
        self.api_url = api_url.rstrip("/")
        
        self.headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"

    def fetch_issues(self, days_limit: int = None, state: str = "open") -> List[Dict[str, Any]]:
        """Fetch open issues from the GitHub repository."""
        url = f"{self.api_url}/repos/{self.repo}/issues"
        
        params = {
            "state": state,
            "sort": "updated",
            "direction": "desc",
            "per_page": 50 # Limit per page to keep it fast
        }
        
        if days_limit:
            since = datetime.now(timezone.utc) - timedelta(days=days_limit)
            params["since"] = since.isoformat()
            
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        
        raw_issues = response.json()
        result = []
        
        for issue_data in raw_issues:
            # GitHub API returns pull requests in the issues list.
            # We filter them out to analyze only real issues.
            if "pull_request" in issue_data:
                continue
                
            issue_number = issue_data["number"]
            discussions = self.fetch_comments(issue_number)
            
            result.append({
                "id": issue_number,
                "title": issue_data["title"],
                "description": issue_data.get("body") or "",
                "web_url": issue_data["html_url"],
                "author": issue_data["user"]["login"] if issue_data.get("user") else "unknown",
                "assignees": [a["login"] for a in issue_data.get("assignees", [])] if issue_data.get("assignees") else [],
                "labels": [l["name"] for l in issue_data.get("labels", [])] if issue_data.get("labels") else [],
                "state": issue_data["state"],
                "created_at": issue_data["created_at"],
                "updated_at": issue_data["updated_at"],
                "discussions": discussions
            })
            
        return result

    def fetch_comments(self, issue_number: int) -> List[List[Dict[str, Any]]]:
        """Fetch comments for a specific GitHub issue."""
        url = f"{self.api_url}/repos/{self.repo}/issues/{issue_number}/comments"
        
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        
        comments_data = response.json()
        
        # GitHub issue comments are a flat list. We map it to a single conversation thread.
        thread = []
        for comment in comments_data:
            thread.append({
                "author": comment["user"]["login"] if comment.get("user") else "unknown",
                "created_at": comment["created_at"],
                "body": comment.get("body") or "",
                "is_system": False
            })
            
        return [thread] if thread else []
