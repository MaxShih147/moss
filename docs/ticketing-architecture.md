# Danny Bot v2 — 內部工單系統架構

> 本文件描述 Danny Bot 從「只讀 RAG 問答」升級為「完整 IT Helpdesk 工單系統」的架構設計。
>
> 作者：Max Shih｜版本：v2.0｜日期：2026-04-24

---

## 1. 目標

把目前「Helpdesk.xlsx 手工維護 + bot 只能讀歷史」的模式，升級為：

1. **結構化資料**：工單、權責、人員、狀態都有正規欄位，不是一張 xlsx
2. **員工有入口**：可以問 bot、也可以直接填工單表單
3. **IT 有管理介面**：看到新單、指派、回覆、結案，全都在一個地方
4. **權責會變**：指派對象從「規則表」查，不是歷史中誰處理過
5. **處理方式沉澱為知識**：IT 每次結單時，AI 自動把回覆整理成乾淨的「處理方式」，給未來 RAG 使用
6. **完全在 Microsoft 生態內**：不新增第三方系統，資料留在 Phrozen 租戶

---

## 2. 架構總覽

```
            ┌──────────────────────────────────────────────────────────┐
            │                     Microsoft 365 租戶                     │
            │                                                          │
            │  ┌──────────────────────┐    ┌──────────────────────┐    │
            │  │  SharePoint List 1   │    │  SharePoint List 2   │    │
            │  │  Systems (權責表)    │    │  Tickets (工單)      │    │
            │  └──────────▲───────────┘    └──────────▲───────────┘    │
            │             │                           │                │
            │             └──────────┬────────────────┘                │
            │                        │                                 │
            │                ┌───────┴────────┐                        │
            │                │   Graph API    │                        │
            │                └───────┬────────┘                        │
            │                        │                                 │
            │     ┌──────────────────┼──────────────────┐              │
            │     │                  │                  │              │
            │  ┌──┴──────┐    ┌──────┴────────┐  ┌──────┴─────────┐    │
            │  │ Power   │    │  Danny Bot    │  │  SharePoint    │    │
            │  │Automate │    │  (Python app) │  │  內建 UI       │    │
            │  │         │    │               │  │  (IT 管理)     │    │
            │  │  通知 / │    │  - 問答 (RAG) │  │                │    │
            │  │  觸發   │    │  - 建單       │  └────────────────┘    │
            │  │  摘要   │    │  - 查單       │                        │
            │  └──┬──────┘    │  - AI 摘要    │                        │
            │     │           └──────┬────────┘                        │
            │     │                  │                                 │
            │     │           ┌──────┴────────┐                        │
            │     │           │   Chroma      │                        │
            │     │           │   (RAG 索引)  │                        │
            │     │           └───────────────┘                        │
            │     │                                                    │
            └─────┼────────────────────────────────────────────────────┘
                  │
          ┌───────┴────────┐
          │  Teams 頻道    │
          │  (通知 IT)     │
          └────────────────┘
```

- **Bot 不再直接讀 xlsx**，而是讀 SharePoint Lists（透過 Graph API）
- **Chroma 索引**改成從 Tickets List 同步（定期 rebuild），內容是「處理方式」而非原始 Reply
- **Power Automate** 負責所有「事件驅動」邏輯：新單通知、結單觸發摘要
- **SharePoint 內建 UI** 就是 IT 的管理介面，不需要寫新 web app

---

## 3. 資料模型

### 3.1 List 1: `Systems`（權責表）

| 欄位 | 型別 | 必填 | 範例 | 說明 |
|---|---|---|---|---|
| `Title` | 單行文字 | ✅ | `Outlook` | 系統／問題分類（對應舊 xlsx 的「系統 System」） |
| `PrimaryOwner` | 人員 | ✅ | Leny | 主要負責人（IT 部門成員） |
| `BackupOwner` | 人員 | ⬜ | Jasam | 備援，主要負責人不在時轉派 |
| `Category` | 選單 | ⬜ | `軟體 / 硬體 / 帳號 / 網路` | 未來做分析用 |
| `Keywords` | 多行文字 | ⬜ | `outlook, 信件, 收信` | bot 意圖判斷用（可選） |
| `IsActive` | 是／否 | ✅ | Yes | 停用某類時不用刪，設 No 即可 |

**預期筆數**：20-50 筆（對應目前資料中看到的系統類別）。

**初始資料**（從歷史推導）：

```
Outlook       → Leny (Primary) / Jasam (Backup)
ERP           → Leny / Jasam
BPM           → Leny / Jasam
NAS           → Jasam / Leny
VPN           → Danny / Leny
印表機        → Jasam / Leny
...
```

實際分配請 IT 部門自己填。

### 3.2 List 2: `Tickets`（工單）

| 欄位 | 型別 | 必填 | 範例 | 說明 |
|---|---|---|---|---|
| `Title` | 單行文字 | ✅ | 自動：`[BPM] 出差費用按不出去` | 系統分類 + 簡短描述 |
| `Requester` | 人員 | ✅ | Chiu Shirley | 報修人 |
| `System` | 查閱 → List 1 | ✅ | BPM | 連結到 Systems List |
| `Description` | 多行文字 | ✅ | 完整問題描述 | bot 從對話擷取或員工自填 |
| `Source` | 選單 | ✅ | `Bot / Form / Manual` | 工單建立來源 |
| `Status` | 選單 | ✅ | `New / Assigned / InProgress / Done / Rejected` | 工單狀態 |
| `Assignee` | 人員 | ⬜ | Leny | 實際處理人（建立時自動從 Systems.PrimaryOwner 帶入） |
| `Reply` | 多行文字 | ⬜ | IT 的處理過程 log | 原始紀錄（可能零碎） |
| `Resolution` | 多行文字 | ⬜ | AI 摘要結果 | **Status → Done 時 AI 自動摘要 Reply 產生** |
| `Attachments` | 附件 | ⬜ | 截圖等 | SharePoint 原生附件功能 |
| `CreatedAt` | 日期時間 | ✅ | 2026-04-24 | 自動 |
| `CompletedAt` | 日期時間 | ⬜ | 2026-04-24 | 狀態變 Done 時自動填 |
| `RejectReason` | 多行文字 | ⬜ | 重複單 | Status=Rejected 時填 |

### 3.3 權限模型

- **Systems List**
  - IT 部門：完整控制
  - 全公司：唯讀（或不可見，由 bot 代為查詢即可）

- **Tickets List**
  - IT 部門：完整控制
  - 全公司：**只能看／編輯自己報的單**（SharePoint List 支援「Read items that were created by the user」設定）
  - Bot service principal：完整控制（透過 Graph API）

### 3.4 舊歷史的遷移

- 780 筆 `Helpdesk.xlsx` 舊工單 → 匯入 `Tickets` List
- `Status` = `Done`
- `Reply` = 原 xlsx 的「回覆」欄（如有）
- `Resolution` = 對有「回覆」的部份跑 AI 摘要（約 233 筆，其餘留空）
- `Source` = `Manual`

---

## 4. 元件與流程

### 4.1 Danny Bot（升級）

新增能力：

| 能力 | 觸發 | 實作 |
|---|---|---|
| 建單 | 使用者說「幫我開單」、「我要報修」，或 bot 答不出來主動詢問 | 多輪對話收集系統+描述，呼叫 Graph API POST 到 Tickets List |
| 查自己的單 | 「我的單」、「我的工單」 | Graph API 查 Tickets where Requester = 當前用戶 |
| 查詢時補當前負責人 | 每次 RAG 答題時 | 從 Systems List 查 PrimaryOwner，覆蓋歷史裡的名字 |
| AI 摘要處理方式 | Power Automate 呼叫 `/api/summarize` | 讀 Ticket → LLM 摘要 → 寫回 `Resolution` |

### 4.2 SharePoint Lists（資料層）

- **Tickets List**：IT 的主要工作介面
- 可以在 Teams 的 IT 部門頻道新增「SharePoint List」分頁 → IT 整天在 Teams 裡就順手管單
- 內建功能免費可用：
  - 排序／篩選／分組（依 Status、Assignee）
  - Grid view / Kanban view
  - 欄位驗證
  - 版本歷史（誰改了什麼）
  - 權限控管
  - 附件支援

### 4.3 Power Automate（事件驅動層）

定義三個 Flow：

**Flow 1: 新工單通知**
```
Trigger: Tickets List - When item is created
Action:  Post message to Teams channel "IT-Helpdesk"
         訊息模板：
         @{Assignee} 新工單 #{ID}
         類別：{System}   報修人：{Requester}
         {Description}
         [ 查看工單 ]({item_url})
```

**Flow 2: 結單觸發 AI 摘要**
```
Trigger: Tickets List - When item is modified,
         Filter: Status = "Done" AND Resolution is empty
Action:  HTTP POST -> https://<bot-public-url>/api/summarize
         Body: { "ticketId": @{ID} }
```

**Flow 3（選配）: SLA 提醒**
```
Trigger: Scheduled daily
Action:  Query Tickets where Status=New AND CreatedAt > 24h ago
         Post 提醒到 IT Teams 頻道
```

### 4.4 AI 摘要（新端點）

在 `app.py` 新增路由：

```python
APP.router.add_post("/api/summarize", summarize_ticket)
```

邏輯：
1. 驗證 Power Automate 的 auth（shared secret）
2. Graph API 取 ticket → 讀 `Description` + `Reply`
3. 呼叫 OpenAI 摘要 prompt：
   ```
   你是 IT 工單助理。根據以下原始處理紀錄，寫一段精簡的「處理方式」
   （2-4 句中文），讓未來遇到同樣問題的人能快速參考。

   問題：{Description}
   原始處理紀錄：{Reply}

   要求：
   - 寫結論，不要流水帳
   - 點出 root cause 和解法
   - 若需聯絡廠商／同事，寫出來
   ```
4. 結果寫回 `Resolution` 欄位
5. 觸發 RAG 索引更新（加這一筆到 Chroma）

### 4.5 RAG 索引更新

**舊做法**：xlsx → parquet → build_index.py → Chroma（一次性）

**新做法**：
- 主資料源：SharePoint Tickets List
- 索引內容：只 embed `Resolution` 已填、Status=Done 的工單
- 更新策略：
  - **即時**：AI 摘要完成後立刻 append 到 Chroma
  - **兜底**：每日排程 full rebuild（launchd on Mac mini）

```python
# 偽代碼
def incremental_index(ticket_id):
    ticket = graph.get_ticket(ticket_id)
    text = build_embed_text(ticket)   # [System] Description + Resolution
    vec = openai.embed(text)
    chroma.upsert(id=ticket_id, vector=vec, metadata={...})
```

---

## 5. 使用者情境

### 5.1 員工提問（最常見）

```
員工 (Teams): Outlook 一直收不到信
Bot: [查 RAG，找到相似歷史 + 查 Systems List]
     您好，Outlook 收信問題常見解法是：
     1. 檢查垃圾郵件
     2. 檢查連線
     3. 重啟 Outlook

     如果以上無效，這類問題由 Leny 處理（Email: leny@...）
     要不要我幫您開一張工單？

員工: 好，幫我開單
Bot: 請簡短描述問題（1-2 句）：
員工: 從早上 9 點開始 Outlook 就收不到信，重啟也沒用

Bot: [呼叫 Graph API，建 Ticket]
     工單 #1247 已建立 ✓
     類別：Outlook
     負責人：Leny
     狀態：Assigned

     Leny 會儘快處理，您可以隨時問我「我的單」查進度。
```

### 5.2 員工查自己的單

```
員工: 我的單
Bot: 您目前有 2 張單：
     #1247 [Outlook] Outlook 收不到信    Assigned → Leny
     #1198 [印表機] 2F 印表機無法列印    Done

員工: 1247 好了沒
Bot: 狀態：Assigned（已指派給 Leny，尚未處理）
```

### 5.3 IT 處理工單

```
1. Leny 在 Teams IT 頻道看到通知（Power Automate 發的）
   @Leny 新工單 #1247 ...

2. Leny 點連結 → SharePoint List 開啟工單
   - Status: Assigned → InProgress
   - 開始處理，把過程記在 Reply 欄（可多次存檔）

3. 處理完：
   - Status: InProgress → Done
   - （Power Automate 觸發）→ Bot /api/summarize
   - AI 讀 Reply，產生 Resolution 寫回

4. 員工下次問類似問題 → RAG 就會用到這個新摘要
```

### 5.4 權責換人

```
情境：Leny 離職，Outlook 改由 Wade 負責

IT Manager:
1. 進 Systems List
2. 找到 Outlook 那一列
3. PrimaryOwner 改成 Wade

→ 下次有員工問 Outlook 問題，bot 答案立刻說「這類問題由 Wade 處理」
→ 新開的 Outlook 工單自動指派給 Wade

完全不用動 bot 程式碼、不用動 xlsx、不用重建索引。
```

---

## 6. 權限與部署

### 6.1 Graph API 權限

Bot 需要用 **Application permissions** 呼叫 Graph API（不綁任何員工帳號）。

**推薦**：`Sites.Selected`（只對指定 site 有權限，最小權限原則）

設定步驟（由 tenant admin 執行）：

1. Azure AD → App registrations → `moss-bot-dev`
2. API permissions → Microsoft Graph → Application permissions → `Sites.Selected`
3. Admin consent
4. 透過 Graph API / PowerShell，對特定 site 授予該 app 的讀寫權限：
   ```powershell
   Grant-PnPAzureADAppSitePermission `
     -AppId "<moss-bot-dev app id>" `
     -DisplayName "Danny Bot" `
     -Site "https://phrozen3d.sharepoint.com/sites/it" `
     -Permissions Write
   ```
   或用 Graph API 等價 endpoint。

**備選**：`Sites.ReadWrite.All`（全租戶所有 SharePoint site 都能讀寫）—— 權限較大，但不需要逐個 site 授權，admin 可能比較願意批。

### 6.2 新增的環境變數

```
GRAPH_TENANT_ID=<同 MicrosoftAppTenantId>
GRAPH_CLIENT_ID=<同 MicrosoftAppId 或獨立 app id>
GRAPH_CLIENT_SECRET=<Azure AD app 的 secret>
SHAREPOINT_SITE_ID=<target site 的 GUID>
SYSTEMS_LIST_ID=<List 1 的 GUID>
TICKETS_LIST_ID=<List 2 的 GUID>
SUMMARIZE_SHARED_SECRET=<給 Power Automate 呼叫 bot 用的 shared secret>
```

### 6.3 依賴套件新增

```
msal>=1.24.0           # Azure AD auth
httpx>=0.25.0          # Graph API calls
```

### 6.4 程式碼結構

```
moss/
  app.py
  bot.py
  llm/                  (現有)
  rag/                  (現有，會改)
  data/                 (現有，遷移用)
  sharepoint/           (新增)
    __init__.py
    auth.py             MSAL client credentials flow
    graph.py            Graph API wrapper
    systems.py          Systems List CRUD
    tickets.py          Tickets List CRUD
  ticketing/            (新增)
    __init__.py
    create.py           建單流程
    query.py            查單流程
    summarize.py        AI 摘要
  scripts/
    migrate_xlsx_to_list.py   (新增) 780 筆歷史匯入
    bulk_summarize.py         (新增) 歷史工單批次 AI 摘要
    refresh.sh                (現有)
  docs/
    ticketing-architecture.md (本檔)
```

---

## 7. 實做分階段

```
Phase 2.0  權責表上線              0.5 天  (我改 bot + 你建 List 1)
Phase 2.1  建單流程                 2 天   (我寫建單對話 + 你建 List 2)
Phase 2.2  新工單通知 (Power Automate) 0.5 天  (你設 Flow)
Phase 2.3  員工查單                1 天   (我寫查詢對話)
Phase 2.4  AI 摘要處理方式         1.5 天  (我寫 endpoint + 你設 Flow)
Phase 2.5  歷史 xlsx 遷移 + 批次摘要 1 天   (我寫 migration script)
Phase 2.6  RAG 切到 List 為資料源   0.5 天  (我改 retriever)
─────────────────────────────────────
總計                                ~7 天人日（純工時）
```

**實際時程**會受這些因素影響：
- Graph API 權限批准（tenant admin 時間）
- Danny / IT 部門訪談：欄位設計、權責分配
- 實際測試與迭代

保守估 **2-3 週**。

---

## 8. 風險與假設

### 風險

| # | 風險 | 影響 | 緩解 |
|---|---|---|---|
| R1 | IT 部門不願換工具 | 整個專案停擺 | Phase 2.0 做個原型先給 Danny 看 |
| R2 | Graph API 權限批不下來 | bot 無法讀寫 Lists | 備案：退回到 OneDrive sync + 腳本更新 |
| R3 | 員工覺得 bot 問答不準而繞過它 | 工單仍靠 Excel 手建 | AI 摘要補齊知識庫、初期 bot 答不好時直接建單流暢 |
| R4 | Power Automate Flow 壞掉沒被發現 | 通知漏發、摘要沒跑 | 監控 Flow 執行歷史，加失敗告警 |
| R5 | SharePoint List 效能瓶頸 | 工單 >5000 筆後查詢慢 | List view threshold 預設 5000，達到再調整或改 Dataverse |

### 假設

- Phrozen 是 Microsoft 365 租戶（已確認）
- IT 部門 <= 10 人
- 年工單量 < 3000 筆（依 780 筆/年推算）
- 員工已習慣用 Teams
- Bot 部署在 Mac mini（或類似 always-on 機器）

---

## 9. 不做的事（明確排除）

為了避免 scope creep，以下**現階段不做**：

- ❌ 員工打電話／傳真建單
- ❌ 工單轉 email（Teams 通知就夠了）
- ❌ 複雜工作流（審核鏈、多級核准）
- ❌ 客戶／外部使用者報修
- ❌ Bot 多語系（只支援繁中）
- ❌ SLA 自動違規罰則、績效排行榜
- ❌ 多 LLM 比較、自己訓模型

這些都是「可以做但現在不做」。未來需求穩定後再評估。

---

## 10. 成功指標

**Phase 2 上線 4 週後**：
- 80% 的工單從 bot 流程建立（不再靠 IT 手建）
- Resolution 欄填寫率 ≥ 70%（IT 願意花時間結單）
- Bot 答題準確率提升（對比 Phase 1，因為 Resolution 比原始 Reply 乾淨）
- 員工回饋：「知道該找誰」的感覺變具體

**Phase 2 上線 3 個月後**：
- 歷史 + 新工單總量 ≥ 1500 筆（RAG 知識庫翻倍）
- IT 部門至少一人主動提出欄位／流程改動建議（代表他們有在用）
