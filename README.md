# Danny Bot — IT Helpdesk Copilot for Microsoft Teams

Danny Bot 是一個部署在 Microsoft Teams 的 IT Helpdesk Copilot，結合歷史報修紀錄、SOP/FAQ 文件與雲端 LLM API，為員工提供即時 IT 問題解答、工單管理與知識回饋循環。

---

## Project Status

**Phase 1: MVP — 基礎 Teams Bot**（進行中）

目前為最小可運行的 Teams Bot，具備訊息收發能力，尚未接入 LLM 與 RAG。

---

## Architecture Overview

完整架構設計請參閱 [ARCHITECTURE.md](./ARCHITECTURE.md)。

### System Flow

```
Employee (Teams)
      │
      ▼
  Teams Bot (Bot Framework SDK)
      │
      ▼
  Internal Gateway
      │
      ├── Intent Router ─────────── 意圖辨識（新問題/查工單/轉派/閒聊）
      ├── Retrieval Layer ───────── 混合檢索（BM25 + Embedding）
      │     ├── Helpdesk History     歷史報修紀錄（Helpdesk.xlsx）
      │     ├── SOP / FAQ / Docs     標準作業程序、常見問答
      │     └── Knowledge Items      已結案轉化的知識條目
      ├── PII Masker ───────────── 個資遮罩（員工ID、Email、主機名）
      ├── Prompt Builder ────────── 組裝 Prompt（檢索結果 + 遮罩後問題）
      ├── LLM Adapter Layer ─────── 呼叫雲端 LLM API
      │     ├── Claude API           （主要）
      │     ├── ChatGPT API          （備援）
      │     └── Grok API             （備援）
      ├── Policy Guard ──────────── 強制轉派規則（硬體/權限/低信心）
      ├── Ticket Service ────────── 工單建立、狀態追蹤、指派
      ├── Knowledge Loop ────────── 結案 → AI 轉知識條目 → 回饋檢索
      └── Logging Service ───────── 對話紀錄、檢索日誌、審計
```

### Answer Strategy — 三級回答制

| 等級 | 條件 | 動作 |
|------|------|------|
| Level 1: 直接回答 | FAQ 命中、高相似歷史案例、SOP 支持 | 直接回覆解答 |
| Level 2: 條件回答 | 需確認狀態、多種可能原因 | 回覆 + 附帶排錯步驟 |
| Level 3: 轉派人工 | 硬體/權限/資料異常/低信心 | 建立工單，通知 IT 人員 |

### Core Strategy

- **Copilot First, Not Autonomous Agent** — Phase 1 是輔助工具，不是自主代理
- **Cloud LLM + Adapter Layer** — 透過統一介面呼叫多家 LLM，避免廠商鎖定
- **Grounded Answers** — 優先使用檢索內容回答，不憑空生成
- **PII Protection** — 所有送往雲端 LLM 的資料經過個資遮罩

---

## Project Structure

```
moss/
├── app.py               # Application entry point — aiohttp web server
│                        # 接收 Teams webhook POST /api/messages
│                        # 初始化 BotFrameworkAdapter 與 DannyBot
│
├── bot.py               # DannyBot class — 核心 Bot 邏輯
│                        # on_message_activity: 處理使用者訊息
│                        # on_members_added_activity: 歡迎訊息
│
├── requirements.txt     # Python dependencies
├── .env.example         # 環境變數範本（Azure Bot credentials）
├── .gitignore           # Git ignore rules
└── ARCHITECTURE.md      # 完整架構設計文件
```

### Planned Structure（Phase 1 完整目標）

```
moss/
├── app.py                        # Entry point
├── bot.py                        # Bot event handler
├── config.py                     # Configuration management
│
├── gateway/                      # Internal Gateway — 核心業務邏輯
│   ├── __init__.py
│   ├── intent_router.py          # 意圖路由（第一決策節點）
│   ├── session_manager.py        # 對話 Session 管理
│   ├── retrieval_orchestrator.py # 檢索協調器
│   ├── prompt_builder.py         # Prompt 組裝 + PII 遮罩
│   ├── policy_guard.py           # 強制轉派 / 安全規則
│   └── response_router.py        # 回應決策（回答/追問/轉派）
│
├── llm/                          # LLM Adapter Layer
│   ├── __init__.py
│   ├── base.py                   # Abstract LLM interface
│   ├── anthropic_provider.py     # Claude API
│   ├── openai_provider.py        # ChatGPT API（reserved）
│   └── xai_provider.py           # Grok API（reserved）
│
├── retrieval/                    # Retrieval Layer
│   ├── __init__.py
│   ├── bm25.py                   # Keyword / BM25 search
│   ├── embedding.py              # Vector similarity search
│   └── hybrid.py                 # Hybrid retrieval strategy
│
├── ticket/                       # Ticket Service
│   ├── __init__.py
│   ├── service.py                # CRUD operations
│   └── models.py                 # Data models
│
├── knowledge/                    # Knowledge Loop
│   ├── __init__.py
│   ├── importer.py               # Helpdesk.xlsx import pipeline
│   ├── augmenter.py              # AI augmentation（歷史紀錄 → 知識條目）
│   └── models.py                 # Data models
│
├── data/                         # Data & preprocessing
│   ├── helpdesk.xlsx             # Original helpdesk records（不進 git）
│   └── preprocessing/
│       ├── field_mapper.py       # Excel field mapping
│       ├── normalizer.py         # System name / status normalization
│       └── quality_filter.py     # Low-quality reply detection
│
├── db/                           # Database
│   ├── __init__.py
│   ├── connection.py             # DB connection management
│   └── migrations/               # Schema migrations
│
├── tests/                        # Tests
│   ├── test_bot.py
│   ├── test_intent_router.py
│   └── test_retrieval.py
│
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
└── ARCHITECTURE.md
```

---

## Data Design

### Database Tables

系統使用 7 張核心資料表：

| Table | 用途 | 主要欄位 |
|-------|------|---------|
| `cases` | 標準化的歷史報修紀錄 | case_id, system_normalized, question_raw, reply_raw, quality_score, is_reusable |
| `knowledge_items` | AI 轉化後的知識條目 | knowledge_id, title, problem_summary, resolution_steps, keywords, embedding_ref |
| `tickets` | 工單 | ticket_id, title, summary, priority, status, assignee, needs_handoff |
| `messages` | 對話訊息 | message_id, ticket_id, sender_type, content, masked_content |
| `retrieval_logs` | 檢索紀錄 | log_id, query_text, retrieved_case_ids, ranking_scores |
| `feedback` | 使用者回饋 | feedback_id, ticket_id, user_helpful, user_comment |

### Data Sources

| 來源 | 說明 |
|------|------|
| Helpdesk.xlsx | Danny 的歷史報修紀錄，包含報修時間、系統、問題描述、處理回覆 |
| SOP / FAQ / Docs | ERP、BPM、Outlook、NAS、印表機、VPN 等標準作業文件 |
| Knowledge Items | 結案後 AI 轉化的標準知識條目，持續累積 |

### Helpdesk.xlsx Import Pipeline

```
Helpdesk.xlsx → Field mapping → Cleaning → Normalization → Quality scoring → Case records → AI augmentation → Vectorization
```

- **System normalization**: `outlook` / `Outlook` → `Outlook`、`印表機` / `列印機` → `Printer`
- **Status normalization**: `V` / `v` → `Closed`、blank → `Open`
- **Low-quality reply detection**: 「已處理」「OK」「已協助」等空泛回覆標記為需 AI 增補

---

## API Endpoints

### Bot API
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/messages` | Teams Bot webhook — 接收所有 Teams 訊息 |

### Planned APIs（Phase 1-2）
| Method | Path | Description |
|--------|------|-------------|
| POST | `/retrieve/search` | 混合檢索（BM25 + embedding） |
| POST | `/llm/generate-answer` | LLM 生成回答 |
| POST | `/llm/classify` | 問題分類 |
| POST | `/llm/followup` | 追問建議 |
| POST | `/llm/augment-knowledge` | 知識增補 |
| POST | `/tickets` | 建立工單 |
| GET | `/tickets/{ticket_id}` | 查詢工單 |
| POST | `/tickets/{ticket_id}/close` | 結案 |
| POST | `/tickets/{ticket_id}/handoff` | 轉派 |
| POST | `/knowledge/import-excel` | 匯入 Excel |
| POST | `/knowledge/augment` | AI 增補知識 |
| GET | `/knowledge/search` | 知識搜尋 |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Bot Framework | Microsoft Bot Framework SDK for Python |
| Web Server | aiohttp |
| LLM API | Anthropic Claude（primary）, OpenAI（reserved）, xAI Grok（reserved） |
| Retrieval | BM25 + Vector embedding（hybrid）— 具體實作 TBD |
| Vector DB | TBD（candidates: ChromaDB, Qdrant, FAISS） |
| Database | TBD（candidates: SQLite for MVP, PostgreSQL for production） |
| PII Masking | Custom regex + rule-based masking |
| Deployment | Mac mini（current）/ Azure App Service（under discussion） |
| Tunnel | ngrok or cloudflared（for local dev） |

---

## Development Phases

### Phase 0: Data Validation ⬜
- [ ] Import Helpdesk.xlsx
- [ ] Field cleaning & normalization
- [ ] Low-quality reply detection
- [ ] Validate usable data ratio
- [ ] Generate first-version knowledge JSON

### Phase 1: Answerable Teams Bot 🔨 ← Current
- [x] Teams Bot basic entry point (echo bot)
- [ ] Azure Bot Service registration
- [ ] Tunnel setup (ngrok/cloudflared)
- [ ] Teams channel integration test
- [ ] Intent Router implementation
- [ ] Retrieval Layer MVP (BM25 + embedding)
- [ ] Single LLM provider integration (Claude)
- [ ] PII Masking
- [ ] Prompt Builder
- [ ] Answer / follow-up / handoff flow

### Phase 2: Ticket & Feedback ⬜
- [ ] Ticket DB & CRUD
- [ ] IT Channel notifications (Adaptive Cards)
- [ ] Ticket query interface
- [ ] User feedback (helpful / not helpful)
- [ ] Retrieval logging

### Phase 3: Knowledge Loop ⬜
- [ ] Post-closure knowledge conversion
- [ ] IT staff confirmation workflow
- [ ] Continuous vector DB updates
- [ ] High-frequency FAQ extraction

### Phase 4: Advanced ⬜
- [ ] Multi-LLM provider switching
- [ ] Cost control & routing
- [ ] Answer quality evaluation
- [ ] Department dashboard (Web UI)
- [ ] Multi-channel expansion evaluation

---

## Setup & Run

### Prerequisites
- Python 3.9+
- Microsoft Azure account (for Bot Channel Registration)
- ngrok or cloudflared (for local development tunnel)

### Installation

```bash
# Clone
git clone <repo-url>
cd moss

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Azure Bot credentials
```

### Run Locally

```bash
source .venv/bin/activate
python app.py
# Bot starts on http://localhost:3978
```

### Connect to Teams (requires Azure setup)

1. **Azure Portal**: Create a Bot Channel Registration
   - Get `MicrosoftAppId` and `MicrosoftAppPassword`
   - Fill in `.env`

2. **Start tunnel**:
   ```bash
   ngrok http 3978
   # or
   cloudflared tunnel --url http://localhost:3978
   ```

3. **Set messaging endpoint** in Azure Bot Settings:
   ```
   https://<your-tunnel-url>/api/messages
   ```

4. **Enable Teams channel** in Azure Bot → Channels → Microsoft Teams

5. **Install bot in Teams**:
   - Teams Admin Center → Manage Apps → Upload custom app
   - Or use App Studio to create a Teams app manifest

### Test Without Azure (Bot Framework Emulator)

1. Download [Bot Framework Emulator](https://github.com/Microsoft/BotFramework-Emulator/releases)
2. Run `python app.py`
3. In Emulator: connect to `http://localhost:3978/api/messages`
4. Leave App ID and Password blank for local testing

---

## Architecture Decisions

### Why Cloud LLM (not self-hosted model)?
- 公司不需要維護 GPU 硬體
- 直接使用最強商用模型能力
- 透過 PII 遮罩 + 最小化 context 控制風險
- LLM Adapter Layer 保留切換彈性

### Why Hybrid Retrieval (not embedding-only)?
- IT 問題常包含系統名稱、錯誤代碼、權限名稱等特定關鍵字
- BM25 對精確關鍵字比對更有效
- Embedding 對語意相似但用詞不同的問題更有效
- 兩者結合覆蓋最廣

### Why Copilot (not Autonomous Agent)?
- Phase 1 優先建立信任
- 涉及權限、硬體、帳號問題必須人工介入
- Copilot 模式風險可控，逐步擴展自主能力

### Infrastructure: Mac mini vs Azure (Under Discussion)
- 目前開發在 Mac mini 上進行
- 生產部署方案尚未定案
- 詳見 [ARCHITECTURE.md Section 13](./ARCHITECTURE.md)

---

## Known Gaps & TODOs

1. **Intent Router 需提升為頂層元件** — 目前 message_parser 是子模組，應升級為 Gateway 第一決策節點
2. **Session 管理策略未定義** — timeout、儲存位置、context window 限制
3. **錯誤處理 / 降級策略缺失** — LLM API 掛掉、檢索零結果時的 fallback
4. **Azure 權限確認中** — 公司帳號能否建立 Bot Channel Registration、Teams 能否 sideload custom app

---

## License

Internal project — not for public distribution.
