
在軟體專案管理中，我們最常遇到的痛點就是：**「Issue 天天有人開，但沒人有時間去梳理出全貌。」** 讓一個 AI Agent 當你的「專案秘書」，自動幫你爬 GitHub、分類 Issue、抓出潛在風險並生成報告，可以幫你省下大量的管理成本。

基於我們的最新決策，我們將這個系統定名為 **"GitHub Issue Analyzer Agent"**。以下是調整後的系統架構與實作藍圖：

---

## 🛠 系統架構設計 (System Architecture)

此 Agent 採用輕量化的無伺服器架構，直接在本地端透過 Python 呼叫雲端 API 進行分析：

```
[本地排程 (Cron/Task)]
       │
       ▼
┌──────────────────────────────┐
│  1. 數據採集模組 (GitHub API) │ <─── 透過 GitHub Repo (owner/repo) 抓取 Issues 與 Comments
└──────────────┬───────────────┘
               │ (JSON Data)
               ▼
┌──────────────────────────────┐
│  2. 核心大模型 (LLM Engine)   │ <─── 雲端 Gemini API (使用 gemini-2.5-flash)
└──────────────┬───────────────┘      提供高效、高品質的長文本推理與 JSON 結構化輸出
               │ (結構化分析結果)
               ▼
┌──────────────────────────────┐
│  3. 業務邏輯與分類 (Analyzer) │ <─── 偵測技術分歧點、開發阻礙點 (Blockers)
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│  4. 報告生成與發送 (Reporter) │ ───> 產出 Markdown 報告 (.md) / 整合 Slack 或 Discord Webhook
└──────────────────────────────┘
```

### 1. 數據採集模組 (GitHub Data Fetcher)

* **作法：** 利用 Python 的 `requests` 直接呼叫 GitHub REST API，簡潔且不依賴重型外部套件。
* **抓取目標：** 指定 Repo（格式如 `owner/repo`）的 Issue 標題、內容、Labels、Assignees，以及最關鍵的——**底下所有的討論留言 (Comments)**。因為團隊的分歧和細節通常藏在留言裡。
* **安全性與防護：** 支援 `GITHUB_TOKEN`（Personal Access Token），避免匿名存取時觸發 GitHub API 的 Rate Limit。

### 2. 雲端 AI 推理引擎 (Gemini LLM Engine)

* **模型首選：** `gemini-2.5-flash`。
* **優勢：** 擁有極大的 Context Window，處理長篇 Issue 討論毫不費力；且具備極佳的 JSON 結構化輸出能力與低廉的 API 成本。
* **運作邏輯：** 給 LLM 一個強大的 System Instruction，使其以資深系統架構師兼專案經理的角色，產出結構化的 JSON 分析報告。

### 3. 報告生成模組 (Reporting System)

* LLM 輸出的結構化 JSON 資料，會被渲染成排版優美的 Markdown 報告，重點展示「專案健康度儀表板」、「關鍵阻礙點」、「團隊技術分歧警告」與「建議行動清單」。
* 支援 Slack 與 Discord Webhook，將每日分析摘要即時推送至團隊溝通頻道。

---

## 🚀 核心開發步驟與實作檔案

我們已經完成 MVP（最小可行性產品）的開發，檔案結構如下：

1. **[.env](file:///home/kenny/Git_KennySpace/issue_reviewer/.env)**：存放 `GITHUB_REPO`、`GEMINI_API_KEY` 等環境設定。
2. **[config.py](file:///home/kenny/Git_KennySpace/issue_reviewer/config.py)**：負責環境變數的讀取與自動清理（如過濾同一行的中文註解、自動解析完整 GitHub 網址為 `owner/repo`）。
3. **[github_fetcher.py](file:///home/kenny/Git_KennySpace/issue_reviewer/github_fetcher.py)**：串接 GitHub REST API，抓取 Issues 及其 Comments。
4. **[llm_client.py](file:///home/kenny/Git_KennySpace/issue_reviewer/llm_client.py)**：直連 Google Gemini API 進行結構化 JSON 生成。
5. **[analyzer.py](file:///home/kenny/Git_KennySpace/issue_reviewer/analyzer.py)**：設計 System & User Prompts，要求 LLM 分析單一 Issue 並找出跨 Issue 的重複與依賴關係。
6. **[reporter.py](file:///home/kenny/Git_KennySpace/issue_reviewer/reporter.py)**：渲染 Markdown 報告並整合 Webhook 通知。
7. **[main.py](file:///home/kenny/Git_KennySpace/issue_reviewer/main.py)**：CLI 程式入口，支援 `--mock` 測試模式與指定天數或特定 Issue 分析。

---

## 💡 架構師的進階悄悄話：怎麼讓這個 Agent 更有價值？

如果只是單純列出 Issue，那跟看網頁沒兩樣。要讓這個 Agent 真正發揮「20年經驗架構師」的威力，我們加入了以下**特徵工程 (Feature Engineering)**：

* **分歧與情緒偵測 (Conflict & Sentiment Detection)：** 讓 Agent 特別去辨識留言中帶有強烈反對意見、語意分歧或情緒起伏的對話（如不同成員對快取 TTL 或是重構時程的爭執），提早對潛在的技術衝突發出預警。
* **阻礙點與風險評估 (Blocker & Risk Identification)：** 辨識程式庫遷移失敗、第三方限制或人員阻礙等實質影響開發進度的項目，並在報告中高亮顯示。
* **跨專案關聯性分析 (Cross-Issue Correlation Mapping)：** 找出 Issues 之間存在的依賴關係（例如：A Issue 必須等待 B Issue 架構定案後才能開始），避免開發人員重複做功或在資訊不對稱下開發。