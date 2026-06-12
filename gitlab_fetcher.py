import requests
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any

class GitLabFetcher:
    def __init__(self, project_id: str, token: str, api_url: str = "https://gitlab.com"):
        """
        Initialize GitLab fetcher using direct REST API requests.
        project_id: GitLab Project ID (e.g., '12345678' or URL-encoded path)
        token: GitLab Personal Access Token (PAT) or Project Access Token
        api_url: GitLab instance URL, defaults to public GitLab
        """
        self.project_id = str(project_id).strip()
        self.token = token
        self.api_url = api_url.rstrip("/")
        
        self.headers = {}
        if self.token:
            self.headers["PRIVATE-TOKEN"] = self.token

    def fetch_issues(self, days_limit: int = None, state: str = "opened") -> List[Dict[str, Any]]:
        """Fetch opened issues from the GitLab repository."""
        url = f"{self.api_url}/api/v4/projects/{self.project_id}/issues"
        
        params = {
            "state": state,
            "order_by": "updated_at",
            "sort": "desc",
            "per_page": 50
        }
        
        if days_limit:
            since = datetime.now(timezone.utc) - timedelta(days=days_limit)
            params["updated_after"] = since.isoformat()
            
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        
        raw_issues = response.json()
        result = []
        
        for issue_data in raw_issues:
            issue_iid = issue_data["iid"]
            discussions = self.fetch_discussions(issue_iid)
            
            result.append({
                "id": issue_iid,
                "title": issue_data["title"],
                "description": issue_data.get("description") or "",
                "web_url": issue_data["web_url"],
                "author": issue_data["author"]["username"] if issue_data.get("author") else "unknown",
                "assignees": [a["username"] for a in issue_data.get("assignees", [])] if issue_data.get("assignees") else [],
                "labels": issue_data.get("labels", []),
                "state": issue_data["state"],
                "created_at": issue_data["created_at"],
                "updated_at": issue_data["updated_at"],
                "discussions": discussions
            })
            
        return result

    def fetch_discussions(self, issue_iid: int) -> List[List[Dict[str, Any]]]:
        """Fetch discussions (comments) for a specific GitLab issue."""
        url = f"{self.api_url}/api/v4/projects/{self.project_id}/issues/{issue_iid}/discussions"
        
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        
        discussions_data = response.json()
        threads = []
        
        for disc in discussions_data:
            thread_notes = []
            notes = disc.get('notes', [])
            for note in notes:
                thread_notes.append({
                    "author": note.get('author', {}).get('username', 'unknown'),
                    "created_at": note.get('created_at', ''),
                    "body": note.get('body', '') or "",
                    "is_system": note.get('system', False)
                })
            if thread_notes:
                threads.append(thread_notes)
                
        return threads
