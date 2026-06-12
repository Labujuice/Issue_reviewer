import argparse
import sys
import logging
import requests
from config import Config
from github_fetcher import GitHubFetcher
from gitlab_fetcher import GitLabFetcher
from analyzer import IssueAnalyzer
from reporter import ReportGenerator

# Set up logging format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def check_has_gemini_credentials() -> bool:
    """Check if Gemini API Key is set in configuration."""
    return bool(Config.GEMINI_API_KEY)

def main():
    parser = argparse.ArgumentParser(description="Git/GitHub/GitLab Issue Analyzer Agent")
    parser.add_argument("--days", type=int, help="只分析過去 N 天更新的 Issues")
    parser.add_argument("--issue-id", type=int, help="指定分析單一 Issue ID")
    parser.add_argument("--output", type=str, default="report.md", help="報告輸出 Markdown 檔案路徑")
    parser.add_argument("--slack", action="store_true", help="是否發送 Slack Webhook 通知")
    parser.add_argument("--discord", action="store_true", help="是否發送 Discord Webhook 通知")
    parser.add_argument("--mock", action="store_true", help="使用線上 PX4/px4_msgs 公開專案進行測試分析（需有 Gemini API Key）")
    parser.add_argument("-e", "--env", type=str, default=None, help="指定載入的 .env 檔案路徑 (例如: .env.gitlab)")
    
    args = parser.parse_args()

    # Load configuration from specified env file
    Config.load(args.env)

    logger.info("========================================")
    logger.info("      Issue Analyzer Agent 啟動")
    logger.info("========================================")

    # Validate Gemini credentials (always required now)
    if not check_has_gemini_credentials():
        logger.error("錯誤: 未偵測到 GEMINI_API_KEY 設定。")
        logger.error("請確認您的環境變數或 .env 檔案中已設定 GEMINI_API_KEY。")
        sys.exit(1)

    # 1. Load data
    issues = []
    if args.mock:
        logger.info("模式: [公開專案測試 (PX4/px4_msgs)]")
        logger.info("正在從 GitHub 公開專案 PX4/px4_msgs 抓取最新 5 個 Issues 作為測試資料...")
        fetcher = GitHubFetcher(
            repo="PX4/px4_msgs",
            token=Config.GITHUB_TOKEN,
            api_url=Config.GITHUB_API_URL
        )
        try:
            raw_issues = fetcher.fetch_issues()
            issues = raw_issues[:5]  # Limit to 5 issues to save tokens and prevent API limit issues
            if args.issue_id:
                issues = [i for i in raw_issues if i["id"] == args.issue_id]
                if not issues:
                    logger.error(f"在抓取的 Issues 中找不到指定測試的 Issue ID: {args.issue_id}")
                    sys.exit(1)
        except Exception as e:
            logger.error(f"從 PX4/px4_msgs 抓取測試資料時發生錯誤: {str(e)}")
            sys.exit(1)
    else:
        try:
            Config.validate()
        except ValueError as e:
            logger.error(str(e))
            logger.error("請確認您的環境變數或指定的 .env 檔案設定是否完整！或使用 --mock 參數進行測試。")
            sys.exit(1)

        provider = Config.REPO_PROVIDER
        logger.info(f"模式: [連接 {provider.upper()} API]")

        if provider == "github":
            fetcher = GitHubFetcher(
                repo=Config.GITHUB_REPO,
                token=Config.GITHUB_TOKEN,
                api_url=Config.GITHUB_API_URL
            )
            logger.info(f"正在連線至 GitHub 專案: {Config.GITHUB_REPO}...")
            try:
                if args.issue_id:
                    logger.info(f"正在單獨抓取 GitHub Issue #{args.issue_id}...")
                    headers = {"Accept": "application/vnd.github+json"}
                    if fetcher.token:
                        headers["Authorization"] = f"token {fetcher.token}"
                    url = f"{fetcher.api_url}/repos/{fetcher.repo}/issues/{args.issue_id}"
                    
                    response = requests.get(url, headers=headers)
                    response.raise_for_status()
                    issue_data = response.json()
                    
                    discussions = fetcher.fetch_comments(args.issue_id)
                    issues = [{
                        "id": issue_data["number"],
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
                    }]
                else:
                    logger.info("正在抓取 GitHub 專案的 Open Issues...")
                    issues = fetcher.fetch_issues(days_limit=args.days)
            except Exception as e:
                logger.error(f"從 GitHub 抓取資料時發生錯誤: {str(e)}")
                sys.exit(1)

        elif provider == "gitlab":
            fetcher = GitLabFetcher(
                project_id=Config.GITLAB_PROJECT_ID,
                token=Config.GITLAB_PRIVATE_TOKEN,
                api_url=Config.GITLAB_URL
            )
            logger.info(f"正在連線至 GitLab 專案 ID: {Config.GITLAB_PROJECT_ID}...")
            try:
                if args.issue_id:
                    logger.info(f"正在單獨抓取 GitLab Issue #{args.issue_id}...")
                    headers = {}
                    if fetcher.token:
                        headers["PRIVATE-TOKEN"] = fetcher.token
                    url = f"{fetcher.api_url}/api/v4/projects/{fetcher.project_id}/issues/{args.issue_id}"
                    
                    response = requests.get(url, headers=headers)
                    response.raise_for_status()
                    issue_data = response.json()
                    
                    discussions = fetcher.fetch_discussions(args.issue_id)
                    issues = [{
                        "id": issue_data["iid"],
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
                    }]
                else:
                    logger.info("正在抓取 GitLab 專案的 Open Issues...")
                    issues = fetcher.fetch_issues(days_limit=args.days)
            except Exception as e:
                logger.error(f"從 GitLab 抓取資料時發生錯誤: {str(e)}")
                sys.exit(1)

    logger.info(f"成功取得 {len(issues)} 個 Issues，即將進行 LLM 分析。")

    if not issues:
        logger.info("沒有待分析的 Issues，程式結束。")
        return

    # 2. Run LLM Analysis
    analyses = []
    relationships = {"duplicates": [], "relations": []}
    
    logger.info(f"使用 Gemini 模型: {Config.GEMINI_MODEL}")
    try:
        analyzer = IssueAnalyzer()
        for issue in issues:
            result = analyzer.analyze_issue(issue)
            analyses.append(result)
        
        # Cross-issue analysis
        if len(analyses) > 1:
            relationships = analyzer.analyze_relationships(analyses)
    except Exception as e:
        logger.error(f"LLM 分析階段發生錯誤: {str(e)}")
        sys.exit(1)

    # 3. Generate Report
    logger.info("正在生成 Markdown 報告...")
    markdown_report = ReportGenerator.generate_markdown(analyses, relationships)
    
    # Write to file
    try:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(markdown_report)
        logger.info(f"報告已成功寫入至: {args.output}")
    except Exception as e:
        logger.error(f"寫入報告檔案時發生錯誤: {str(e)}")

    # 4. Send Webhooks
    if args.slack:
        if Config.SLACK_WEBHOOK_URL:
            logger.info("正在發送 Slack Webhook...")
            summary_msg = f"🤖 *{Config.REPO_PROVIDER.upper()} Issue 分析報告已出爐!*\n" \
                          f"📋 共分析了 *{len(analyses)}* 個 Issues。\n" \
                          f"🛑 發現 *{sum(len(a.get('blockers', [])) for a in analyses)}* 個阻礙點，" \
                          f"⚖️ *{sum(1 for a in analyses if len(a.get('conflicts', [])) > 0)}* 個潛在技術分歧。\n" \
                          f"詳細報告已儲存在 `{args.output}` 中。"
            ReportGenerator.send_webhook_notification(Config.SLACK_WEBHOOK_URL, summary_msg, "slack")
        else:
            logger.warning("未設定 SLACK_WEBHOOK_URL，跳過發送。")

    if args.discord:
        if Config.DISCORD_WEBHOOK_URL:
            logger.info("正在發送 Discord Webhook...")
            summary_msg = f"🤖 **{Config.REPO_PROVIDER.upper()} Issue 分析報告已產出**\n" \
                          f"共分析了 **{len(analyses)}** 個 Issues。\n" \
                          f"偵測到阻礙點: {sum(len(a.get('blockers', [])) for a in analyses)} 個 | " \
                          f"技術分歧: {sum(1 for a in analyses if len(a.get('conflicts', [])) > 0)} 個。\n" \
                          f"詳細報告請查看 `{args.output}`。"
            ReportGenerator.send_webhook_notification(Config.DISCORD_WEBHOOK_URL, summary_msg, "discord")
        else:
            logger.warning("未設定 DISCORD_WEBHOOK_URL，跳過發送。")

    logger.info("分析代理任務完成！")

if __name__ == "__main__":
    main()
