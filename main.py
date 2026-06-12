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

# Mock data for out-of-the-box testing
MOCK_ISSUES = [
    {
        "id": 101,
        "title": "API Gateway 在高負載下發生記憶體洩漏 (Memory Leak)",
        "description": "生產環境的 Pod 頻繁被 OOM-killer 終止。記憶體用量隨著請求量呈線性增長。懷疑是最近合併的日誌解析器造成的。",
        "web_url": "https://github.com/mock/project/issues/101",
        "author": "dev_alice",
        "assignees": ["dev_bob"],
        "labels": ["Bug", "Severity::Critical", "Production"],
        "state": "open",
        "created_at": "2026-06-10T10:00:00Z",
        "updated_at": "2026-06-12T15:30:00Z",
        "discussions": [
            [
                {
                    "author": "dev_bob",
                    "created_at": "2026-06-10T11:00:00Z",
                    "body": "我分析了 heap dump，記憶體被大量的日誌快取字串 (log cache strings) 佔滿。日誌解析模組內部使用了靜態快取且沒有設定 TTL。",
                    "is_system": False
                },
                {
                    "author": "arch_carol",
                    "created_at": "2026-06-10T12:00:00Z",
                    "body": "我不建議只是加 TTL。高併發下 TTL 太長一樣會爆記憶體，太短又沒快取效果。我們應該直接重構，移除這個靜態快取，改用串流解析器。",
                    "is_system": False
                },
                {
                    "author": "dev_bob",
                    "created_at": "2026-06-11T09:00:00Z",
                    "body": "可是重構日誌模組需要至少 5 個工作天，我們現在生產環境天天在掛。我反對直接重構，先加一個短 TTL 快速上線止血才是對的。",
                    "is_system": False
                },
                {
                    "author": "arch_carol",
                    "created_at": "2026-06-11T10:30:00Z",
                    "body": "加 TTL 會帶來更難追蹤的 Race Condition 隱患。我強烈不同意這個權宜之計，這是在埋地雷。",
                    "is_system": False
                }
            ]
        ]
    },
    {
        "id": 102,
        "title": "資料庫線上 Migration 腳本在 Replica 節點上超時失敗",
        "description": "在執行 `v2_4_0__user_index.sql` 時，因為鎖定超時 (Lock Wait Timeout) 導致遷移失敗。這影響了我們本週的部署計劃。",
        "web_url": "https://github.com/mock/project/issues/102",
        "author": "ops_dave",
        "assignees": [],
        "labels": ["Deployment", "Severity::High"],
        "state": "open",
        "created_at": "2026-06-11T08:00:00Z",
        "updated_at": "2026-06-12T12:00:00Z",
        "discussions": [
            [
                {
                    "author": "dev_bob",
                    "created_at": "2026-06-11T14:00:00Z",
                    "body": "這是因為 `users` 資料表有 5000 萬筆資料，建立索引時沒有使用 `CONCURRENTLY` (我們是用 PostgreSQL 嗎？)，導致鎖表。",
                    "is_system": False
                },
                {
                    "author": "ops_dave",
                    "created_at": "2026-06-11T14:30:00Z",
                    "body": "我們在 AWS RDS Aurora PostgreSQL 上跑。@dev_bob 說得對，必須用 CONCURRENTLY 建立索引，否則會鎖定寫入。但我發現遷移框架 Flyway 預設不支援 concurrent 模式，會報錯。這是一個 Block 點。",
                    "is_system": False
                }
            ]
        ]
    },
    {
        "id": 103,
        "title": "更新 API Gateway 日誌設定文件",
        "description": "我們需要針對 API Gateway 的日誌解析器設定進行說明文件的更新，特別是 cache 相關設定參數。",
        "web_url": "https://github.com/mock/project/issues/103",
        "author": "writer_eve",
        "assignees": ["writer_eve"],
        "labels": ["Documentation", "Severity::Low"],
        "state": "open",
        "created_at": "2026-06-12T09:00:00Z",
        "updated_at": "2026-06-12T14:00:00Z",
        "discussions": [
            [
                {
                    "author": "arch_carol",
                    "created_at": "2026-06-12T14:10:00Z",
                    "body": "慢著，如果 Issue #101 決定要徹底重構日誌模組並移除 cache 快取，那這些設定值將會被廢棄。建議先等 #101 決定後，再行撰寫文件，避免做白工。",
                    "is_system": False
                }
            ]
        ]
    }
]

# Mock LLM analysis results for quick demo when Gemini API Key is missing
MOCK_ANALYSIS_RESULTS = [
    {
        "id": 101,
        "title": "API Gateway 在高負載下發生記憶體洩漏 (Memory Leak)",
        "web_url": "https://github.com/mock/project/issues/101",
        "summary": "生產環境 API Gateway Pod 因記憶體洩漏頻繁 OOM 終止，問題源於新版日誌解析器的靜態快取無 TTL 限制。",
        "priority": {
            "level": "Critical",
            "reason": "影響生產環境穩定性，導致服務中斷 (OOM-killed)。"
        },
        "blockers": [
            "生產環境 Pod 頻繁重啟，導致連線中斷。"
        ],
        "conflicts": [
            {
                "description": "日誌快取問題修補方案的分歧 (權宜之計 vs 根本重構)",
                "parties": ["dev_bob", "arch_carol"],
                "evidence": "@dev_bob 建議加短 TTL 快上線止血；@arch_carol 反對並主張花 5 天重構，認為加 TTL 會引入 Race Condition 隱患。"
            }
        ],
        "actions": [
            {
                "task": "由架構師與開發人員召開 15 分鐘會議，決定是要重構還是先做熱修復（加 TTL + 監控）。",
                "suggested_assignee": "arch_carol"
            },
            {
                "task": "實施臨時的 Pod 記憶體上限調升以減緩重啟頻率。",
                "suggested_assignee": "dev_bob"
            }
        ]
    },
    {
        "id": 102,
        "title": "資料庫線上 Migration 腳本在 Replica 節點上超時失敗",
        "web_url": "https://github.com/mock/project/issues/102",
        "summary": "Flyway 執行 v2_4_0 遷移時因鎖定超時失敗，主因是 5000 萬筆的 users 表在建立索引時未採用 CONCURRENTLY 模式且 Flyway 預設有限制。",
        "priority": {
            "level": "High",
            "reason": "阻礙了本週的正常部署時程。"
        },
        "blockers": [
            "Flyway 遷移框架預設不支援 PostgreSQL 的 CONCURRENTLY 索引建立模式。"
        ],
        "conflicts": [],
        "actions": [
            {
                "task": "研究並設定 Flyway 允許非交易式的 Migration 或是手動在資料庫背景建立索引後，再標記該 migration 為成功。",
                "suggested_assignee": "ops_dave"
            }
        ]
    },
    {
        "id": 103,
        "title": "更新 API Gateway 日誌設定文件",
        "web_url": "https://github.com/mock/project/issues/103",
        "summary": "更新 Gateway 快取設定文件的任務，目前正等待 #101 的架構方向定案。",
        "priority": {
            "level": "Low",
            "reason": "屬於文件更新，且當前依賴的前置工作尚未定案。"
        },
        "blockers": [
            "等待 #101 API Gateway 記憶體洩漏之架構決定，以防文件設定值過期廢棄。"
        ],
        "conflicts": [],
        "actions": [
            {
                "task": "暫停此工作，待 #101 完成後重新指派。",
                "suggested_assignee": "writer_eve"
            }
        ]
    }
]

MOCK_RELATIONSHIPS = {
    "duplicates": [],
    "relations": [
        {
            "issues": [101, 103],
            "type": "Blocker",
            "reason": "#101 的日誌模組重構決策直接阻礙了 #103 日誌設定文件的撰寫，避免產生廢棄設定的說明。"
        }
    ]
}

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
    parser.add_argument("--mock", action="store_true", help="使用 Mock 測試數據（無需連接 Repo）")
    parser.add_argument("-e", "--env", type=str, default=None, help="指定載入的 .env 檔案路徑 (例如: .env.gitlab)")
    
    args = parser.parse_args()

    # Load configuration from specified env file
    Config.load(args.env)

    logger.info("========================================")
    logger.info("      Issue Analyzer Agent 啟動")
    logger.info("========================================")

    # 1. Load data
    issues = []
    if args.mock:
        logger.info("模式: [測試 Mock 數據 (PX4/px4_msgs)]")
        if check_has_gemini_credentials():
            logger.info("偵測到已設定 Gemini API Key，將動態從 GitHub 公開專案 PX4/px4_msgs 抓取最新 5 個 Issues 進行分析...")
            mock_fetcher = GitHubFetcher(
                repo="PX4/px4_msgs",
                token=Config.GITHUB_TOKEN,
                api_url=Config.GITHUB_API_URL
            )
            try:
                raw_issues = mock_fetcher.fetch_issues()
                issues = raw_issues[:5]
                if args.issue_id:
                    issues = [i for i in raw_issues if i["id"] == args.issue_id]
                    if not issues:
                        logger.error(f"在抓取的 Issues 中找不到 Mock Issue ID: {args.issue_id}")
                        sys.exit(1)
            except Exception as e:
                logger.error(f"從 PX4/px4_msgs 抓取資料時發生錯誤: {str(e)}")
                logger.info("將退回使用預載的靜態 Mock 數據進行測試...")
                issues = MOCK_ISSUES
        else:
            logger.info("未設定 Gemini API Key，將使用內建靜態 Mock 數據...")
            issues = MOCK_ISSUES
            if args.issue_id:
                issues = [i for i in issues if i["id"] == args.issue_id]
                if not issues:
                    logger.error(f"找不到 Mock Issue ID: {args.issue_id}")
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
    
    # Check if we should use mock LLM responses
    use_mock_llm = args.mock and not check_has_gemini_credentials()
    
    if use_mock_llm:
        logger.info("偵測到無 Gemini API Key 設定。為了讓您快速體驗，將使用預先產出的 Mock LLM 分析結果。")
        issue_ids = {i["id"] for i in issues}
        analyses = [a for a in MOCK_ANALYSIS_RESULTS if a["id"] in issue_ids]
        relationships = MOCK_RELATIONSHIPS
    else:
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
