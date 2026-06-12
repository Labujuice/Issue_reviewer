import datetime
import logging
import requests
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class ReportGenerator:
    @staticmethod
    def generate_markdown(analyses: List[Dict[str, Any]], relationships: Dict[str, Any]) -> str:
        """Generate a beautiful, formatted Markdown report in Traditional Chinese."""
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Calculate stats
        total_issues = len(analyses)
        critical_count = sum(1 for a in analyses if a.get("priority", {}).get("level") == "Critical")
        high_count = sum(1 for a in analyses if a.get("priority", {}).get("level") == "High")
        blockers_count = sum(len(a.get("blockers", [])) for a in analyses)
        conflicts_count = sum(1 for a in analyses if len(a.get("conflicts", [])) > 0)
        
        md = []
        md.append(f"# 🤖 GitHub Issues 智能分析報告")
        md.append(f"> **報告產出時間**: `{now_str}` | **分析 Issue 總數**: `{total_issues}` 個\n")
        
        # Dashboard Cards
        md.append("## 📊 專案健康度儀表板")
        md.append("| 指標 | 數據 | 狀態提示 |")
        md.append("| :--- | :---: | :--- |")
        md.append(f"| 🚨 致命 (Critical) Issues | **{critical_count}** | { '⚠️ 需立即介入' if critical_count > 0 else '✅ 正常' } |")
        md.append(f"| 🟠 高優先級 (High) Issues | **{high_count}** | { '🔔 需列入近期規劃' if high_count > 0 else '✅ 正常' } |")
        md.append(f"| 🛑 阻礙點與風險 (Blockers) | **{blockers_count}** | { f'❌ 偵測到 {blockers_count} 個阻礙點' if blockers_count > 0 else '✅ 無阻礙' } |")
        md.append(f"| ⚖️ 意見分歧與爭議 (Conflicts) | **{conflicts_count}** | { f'⚠️ 偵測到 {conflicts_count} 個爭議討論' if conflicts_count > 0 else '✅ 溝通順暢' } |\n")
        
        # 1. Blockers & Risks Section
        all_blockers = []
        for a in analyses:
            for b in a.get("blockers", []):
                all_blockers.append((a["id"], a["title"], a["web_url"], b))
                
        if all_blockers:
            md.append("## 🛑 關鍵阻礙點與開發風險")
            md.append("以下項目目前存在開發阻礙，可能導致專案延遲：")
            for issue_id, title, url, blocker_desc in all_blockers:
                md.append(f"- **[#{issue_id}]({url})** {title}:")
                md.append(f"  - ❌ {blocker_desc}")
            md.append("")
            
        # 2. Conflicts & Disagreements Section
        all_conflicts = []
        for a in analyses:
            for c in a.get("conflicts", []):
                all_conflicts.append((a["id"], a["title"], a["web_url"], c))
                
        if all_conflicts:
            md.append("## ⚖️ 團隊技術分歧與爭議警示")
            md.append("偵測到以下 Issue 討論串中存在技術方案分歧或強烈反對意見，建議架構師/PM 介入調解：")
            for issue_id, title, url, conflict in all_conflicts:
                parties_str = ", ".join(f"`@{p}`" for p in conflict.get("parties", []))
                md.append(f"- **[#{issue_id}]({url})** {title}:")
                md.append(f"  - **爭議焦點**: {conflict.get('description')}")
                md.append(f"  - **參與成員**: {parties_str}")
                md.append(f"  - **具體分歧線索**: *\"{conflict.get('evidence')}\"*")
            md.append("")
            
        # 3. Duplicates & Relations Section
        duplicates = relationships.get("duplicates", [])
        relations = relationships.get("relations", [])
        
        if duplicates or relations:
            md.append("## 🔗 重複與關聯 Issue 偵測")
            if duplicates:
                md.append("### 👥 重複的 Issues (建議合併/關閉)")
                for dup in duplicates:
                    issue_links = ", ".join(f"`#{iid}`" for iid in dup.get("issues", []))
                    md.append(f"- **重複群組 {issue_links}**: {dup.get('reason')}")
                md.append("")
            if relations:
                md.append("### 🔄 跨 Issue 關聯性")
                for rel in relations:
                    issue_links = " ➡️ ".join(f"`#{iid}`" for iid in rel.get("issues", []))
                    md.append(f"- **{issue_links}** ({rel.get('type')}): {rel.get('reason')}")
                md.append("")
                
        # 4. Proposed Action Items
        all_actions = []
        for a in analyses:
            for act in a.get("actions", []):
                all_actions.append((a["id"], a["title"], a["web_url"], act))
                
        if all_actions:
            md.append("## 📋 建議下一步行動清單 (Action Items)")
            md.append("| 來源 Issue | 具體任務 | 建議負責人 | 狀態 |")
            md.append("| :--- | :--- | :---: | :---: |")
            for issue_id, title, url, act in all_actions:
                assignee = act.get("suggested_assignee", "Unassigned")
                assignee_str = f"`@{assignee}`" if assignee != "Unassigned" else "❔ 待指派"
                md.append(f"| [#{issue_id}]({url}) | {act.get('task')} | {assignee_str} | [ ] 未開始 |")
            md.append("")
            
        # 5. Detail Issues Summary
        md.append("## 📄 各 Issue 分析明細")
        # Sort by priority order: Critical -> High -> Medium -> Low -> Unknown
        priority_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3, "Unknown": 4}
        sorted_analyses = sorted(
            analyses, 
            key=lambda x: priority_order.get(x.get("priority", {}).get("level", "Unknown"), 4)
        )
        
        for a in sorted_analyses:
            level = a.get("priority", {}).get("level", "Unknown")
            reason = a.get("priority", {}).get("reason", "")
            
            # Icon mapping for priority
            emoji = "⚪"
            if level == "Critical":
                emoji = "🚨 [Critical]"
            elif level == "High":
                emoji = "🟠 [High]"
            elif level == "Medium":
                emoji = "🟡 [Medium]"
            elif level == "Low":
                emoji = "🟢 [Low]"
                
            md.append(f"### {emoji} [#{a['id']}]({a['web_url']}) {a['title']}")
            md.append(f"- **一句話摘要**: {a.get('summary')}")
            md.append(f"- **優先級理由**: {reason}")
            
            # List actions if any
            if a.get("actions"):
                act_list = []
                for act in a["actions"]:
                    assignee = act.get('suggested_assignee', 'Unassigned')
                    act_list.append(f"{act.get('task')} (指派給: `@{assignee}`)")
                md.append(f"- **行動建議**: {'; '.join(act_list)}")
            md.append("")
            
        return "\n".join(md)

    @staticmethod
    def send_webhook_notification(webhook_url: str, content: str, provider: str = "slack") -> bool:
        """Send notifications to Slack or Discord webhooks."""
        if not webhook_url:
            return False
            
        try:
            if provider == "slack":
                # Slack message payload
                payload = {"text": content}
            elif provider == "discord":
                # Discord message payload
                payload = {"content": content[:2000]} # Limit to 2000 chars
            else:
                logger.warning(f"不支援的 Webhook Provider: {provider}")
                return False
                
            response = requests.post(webhook_url, json=payload, headers={"Content-Type": "application/json"})
            response.raise_for_status()
            logger.info(f"成功發送通知至 {provider} Webhook。")
            return True
        except Exception as e:
            logger.error(f"發送 Webhook 通知時發生錯誤: {str(e)}")
            return False
