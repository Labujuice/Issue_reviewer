import json
import logging
from typing import List, Dict, Any
from llm_client import LLMClient

logger = logging.getLogger(__name__)

class IssueAnalyzer:
    def __init__(self):
        self.llm = LLMClient()

    def analyze_issue(self, issue: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a single issue and return structured analysis result in Traditional Chinese."""
        
        # Format the discussion thread for LLM input
        discussion_text = ""
        if issue.get("discussions"):
            discussion_text += "討論與留言歷程:\n"
            for idx, thread in enumerate(issue["discussions"], 1):
                discussion_text += f"\n--- 討論對話串 #{idx} ---\n"
                for note in thread:
                    system_prefix = "[系統自動產生] " if note.get("is_system") else ""
                    discussion_text += f"- 時間:[{note['created_at']}] 作者:{note['author']}: {system_prefix}{note['body']}\n"
        else:
            discussion_text = "討論與留言歷程: 尚無討論。"

        user_prompt = f"""請分析以下 GitHub Issue 的內容與討論紀錄：

Issue 編號: #{issue['id']}
標題: {issue['title']}
提案者: {issue['author']}
建立時間: {issue['created_at']}
更新時間: {issue['updated_at']}
標籤 (Labels): {', '.join(issue['labels']) if issue['labels'] else '無'}
指派對象 (Assignees): {', '.join(issue['assignees']) if issue['assignees'] else '無'}

描述內容:
{issue['description']}

{discussion_text}
"""

        system_prompt = """你是一位資深的系統架構師兼專案經理。請分析提供的 GitHub Issue 及其討論歷程，從中識別出：
1. 簡短摘要 (summary)：一句話總結該 Issue 當前的狀態或核心問題。
2. 推薦優先級 (priority)：評估優先級級別（Low、Medium、High、Critical），並附上簡短的評估理由。
3. 阻礙點與風險 (blockers)：條列出目前遇到的開發阻礙或潛在技術/時程風險（如缺少外部依賴、技術盲點、無人處理）。若無，請保留空陣列。
4. 討論分歧與技術爭議 (conflicts)：特別識別留言中是否有團隊成員對實作方案、架構設計有不同意見，或是帶有情緒化爭執與質疑。每個爭議需列出：
   - description: 爭議的核心點描述。
   - parties: 參與爭論的成員帳號（如 [username1, username2]）。
   - evidence: 爭論焦點的簡述或代表性發言。
   若無分歧，請保留空陣列。
5. 後續行動與建議 (actions)：具體可執行的下一步工作，並建議最適合處理的成員（如 username 或 'Unassigned'）。

你必須嚴格回傳符合以下 JSON 格式的內容：
{
  "summary": "一句話摘要說明當前狀態。",
  "priority": {
    "level": "Low" | "Medium" | "High" | "Critical",
    "reason": "評估該優先級的理由。"
  },
  "blockers": [
    "阻礙點或風險描述 1",
    "阻礙點或風險描述 2"
  ],
  "conflicts": [
    {
      "description": "技術方案或意見的分歧點描述",
      "parties": ["username1", "username2"],
      "evidence": "成員 A 主張...，但成員 B 認為... 的具體分歧摘要"
    }
  ],
  "actions": [
    {
      "task": "建議的下一步具體任務",
      "suggested_assignee": "建議負責人帳號或 Unassigned"
    }
  ]
}

請確保回傳的內容完全為繁體中文（專有名詞除外），且必須是合法的 JSON 格式。請勿附加任何額外的說明文字或 Markdown 包裝，只輸出 JSON 本身。
"""

        try:
            logger.info(f"正在分析 Issue #{issue['id']}: {issue['title']}...")
            analysis = self.llm.generate_json(system_prompt, user_prompt)
            # 合併 metadata 確保回傳資訊完整
            analysis["id"] = issue["id"]
            analysis["title"] = issue["title"]
            analysis["web_url"] = issue["web_url"]
            return analysis
        except Exception as e:
            logger.error(f"分析 Issue #{issue['id']} 時發生錯誤: {str(e)}")
            return {
                "id": issue["id"],
                "title": issue["title"],
                "web_url": issue["web_url"],
                "summary": f"分析失敗 (錯誤: {str(e)})",
                "priority": {"level": "Unknown", "reason": "分析程式發生例外狀況"},
                "blockers": [],
                "conflicts": [],
                "actions": [],
                "error": str(e)
            }

    def analyze_relationships(self, analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Detect relations or duplicate issues across all analyzed issues in Traditional Chinese."""
        if len(analyses) <= 1:
            return {"duplicates": [], "relations": []}

        summary_list = []
        for a in analyses:
            summary_list.append({
                "id": a["id"],
                "title": a["title"],
                "summary": a.get("summary", "")
            })

        user_prompt = f"""請分析以下已分析完成的 GitHub Issues 清單，判斷彼此之間是否存在重複或關聯性：
{json.dumps(summary_list, ensure_ascii=False, indent=2)}
"""

        system_prompt = """你是一位專案管理大師。請閱讀提供的 Issues 摘要清單，識別：
1. 重複的 Issues (duplicates)：為了解決同一個 bug、或重複提出的相同需求。
2. 關聯的 Issues (relations)：彼此有阻擋關係（Blocker）、或屬於同一模組/底層 bug 引起的不同表現（Related），亦或是有父子任務關係（Parent-Child）。

你必須嚴格回傳符合以下 JSON 格式的內容：
{
  "duplicates": [
    {
      "issues": [123, 125],
      "reason": "說明為什麼這兩個 Issue 是重複的。"
    }
  ],
  "relations": [
    {
      "issues": [123, 128],
      "type": "Blocker" | "Related" | "Parent-Child",
      "reason": "說明兩者之間的關聯理由。"
    }
  ]
}

請確保回傳的內容完全為繁體中文，且必須是合法的 JSON 格式。請勿附加任何額外的說明文字。
"""
        try:
            logger.info("正在分析 Issues 之間的重複與關聯關係...")
            return self.llm.generate_json(system_prompt, user_prompt)
        except Exception as e:
            logger.error(f"分析關聯關係時發生錯誤: {str(e)}")
            return {"duplicates": [], "relations": [], "error": str(e)}
