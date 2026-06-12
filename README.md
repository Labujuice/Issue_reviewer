# 🤖 Multi-Platform Issue Analyzer Agent (Issue 智能分析秘書)

本專案是一個基於 Python 與 Google Gemini API 實作的**跨平台專案 Issue 智能分析工具**。它能自動從 GitHub 或 GitLab 採集 Issues 與留言討論串，透過 LLM 分析其中的技術分歧、進度瓶頸（Blockers）與跨 Issue 的依賴關係，並生成排版美觀的 Markdown 報告，甚至可透過 Webhook 推送通知至 Slack 與 Discord 頻道。

---

## 🌟 核心功能

* 🔌 **多平台支援**：原生支援 GitHub（Public/Private）與 GitLab 專案數據採集。
* 🧠 **雙重分析機制**：
  * **單一 Issue 分析**：自動識別狀態摘要、推薦優先級、潛在開發風險（Blockers）以及討論留言中的技術爭議點（Conflicts & Disagreements）。
  * **跨 Issue 關聯分析**：自動分析所有 Issue 之間的重複性（Duplicates）與依賴/阻擋關係（Relations）。
* 📂 **動態設定檔載入**：支援指定不同的 `.env` 檔案載入（例如 `--env .env.gitlab`），便於其他指令碼或 Agent 觸發不同的專案分析。
* ⚡ **輕量高效**：全部核心功能以 `requests` 直接發送 REST API 請求，無 python-gitlab 或 pygithub 等肥重外部庫依賴，運作快速且乾淨。
* 💬 **社群通知整合**：支援透過 Webhook 發送報告摘要至 Slack 或 Discord 頻道。

---

## 📂 專案結構

```
issue_reviewer/
├── config.py             # 讀取並驗證 .env 設定（支援自訂檔案載入、網址自動解析）
├── github_fetcher.py     # GitHub REST API 連線與 Issues/Comments 採集
├── gitlab_fetcher.py     # GitLab REST API 連線與 Issues/Discussions 採集
├── llm_client.py         # 直連 Google Gemini API (gemini-2.5-flash) 進行結構化 JSON 生成
├── analyzer.py           # 分析核心（定義 System & User Prompts，呼叫 LLM）
├── reporter.py           # 報告生成器（渲染 Markdown）與 Webhook 發送模組
├── main.py               # 程式主入口 (CLI 介面)
├── requirements.txt      # 專案依賴套件說明
├── .env.example          # 環境變數範本檔
└── README.md             # 專案說明文件
```

---

## 🚀 快速開始

### 1. 安裝環境依賴
確保您使用的是 Python 3.10+，並在專案目錄下安裝依賴：
```bash
pip install -r requirements.txt
```

### 2. 配置環境變數
將 [.env.example](.env.example) 複製並重新命名為 `.env`：
```bash
cp .env.example .env
```
編輯 `.env` 並填入您的設定，例如：
```env
REPO_PROVIDER=github
GITHUB_REPO=您的專案（格式為 owner/repo，亦支援貼入完整專案網址）
GEMINI_API_KEY=您的Gemini金鑰
```

### 3. 執行分析

#### 💡 線上動態測試模式 (無需配置自己的專案)
如果您想快速體驗，程式內建了 `--mock` 模式。只要您的 `.env` 內有填寫 `GEMINI_API_KEY`，系統會**自動連接 GitHub 公開專案 [PX4/px4_msgs](https://github.com/PX4/px4_msgs)** 抓取最新的 5 個 Issues 進行即時分析：
```bash
python3 main.py --mock --output mock_report.md
```
*(執行完後，您可以開啟 `mock_report.md` 查看結果。)*

#### 📂 分析您自己的 GitHub 專案
```bash
python3 main.py --output report.md
```

#### 🦊 分析 GitLab 專案 (以指定自訂環境設定檔為例)
1. 建立一個 `gitlab.env`，內容填寫 `REPO_PROVIDER=gitlab` 等 GitLab 對應變數。
2. 執行指令：
   ```bash
   python3 main.py --env gitlab.env --output gitlab_report.md
   ```

---

## 🛠 命令列參數說明 (CLI Arguments)

| 參數 | 捷徑 | 類型 | 說明 |
| :--- | :---: | :---: | :--- |
| `--days` | - | `int` | 只分析過去 N 天內有更新的 Issues（不填則分析全部 Open 狀態的 Issues）。 |
| `--issue-id`| - | `int` | 指定分析單一個 Issue ID / IID 內容。 |
| `--output` | - | `str` | 產出報告的 Markdown 檔案儲存路徑（預設為 `report.md`）。 |
| `--env` | `-e` | `str` | 指定要載入的設定檔路徑（預設為專案根目錄下的 `.env`）。 |
| `--slack` | - | `flag`| 啟用發送 Slack Webhook 通知。 |
| `--discord` | - | `flag`| 啟用發送 Discord Webhook 通知。 |
| `--mock` | - | `flag`| 以 GitHub 公開 Repo [PX4/px4_msgs](https://github.com/PX4/px4_msgs) 進行測試。 |
