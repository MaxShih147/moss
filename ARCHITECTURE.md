# Danny Teams Bot MVP - Architecture Document

---

## 1. Project Overview

### Purpose

Build an IT Helpdesk Bot deployed in **Microsoft Teams**, with a **Mac mini** as Internal AI Gateway / Orchestrator, combining:

- Historical Helpdesk records
- SOP / FAQ / Documents
- Cloud LLM API (Claude / ChatGPT / Grok)
- Ticket / Feedback / Knowledge Loop

### Core Strategy: Copilot First, Not Autonomous Agent

Phase 1 is an **IT Helpdesk Copilot**, not a fully autonomous agent:

- Bot helps understand the problem
- Bot finds historical cases & SOPs
- Bot provides grounded answers
- Bot assists with ticket creation & handoff when needed

### Mac mini Role: Internal AI Gateway / Orchestrator

Not a model host. Its responsibilities:

- Receive Teams Bot messages
- Query Helpdesk / SOP / FAQ / Documents
- Data cleaning & PII masking
- Prompt assembly with retrieval context
- Call Cloud LLM APIs
- Return answers
- Create tickets
- Save logs
- Drive knowledge loop

### Model Strategy: Cloud LLM + Adapter Layer

Use Cloud LLM APIs (ChatGPT / Claude / Grok) through an **LLM Adapter Layer** to:

- Swap model providers
- Route tasks to different models
- Control costs
- Enable A/B testing
- Avoid vendor lock-in

---

## 2. High-Level Architecture

```
Employee in Teams
      |
      v
  Teams Bot
      |
      v
  Internal Gateway (Mac mini)
      |
      +---> Retrieval Layer ---> Helpdesk History
      |                    +---> SOP / FAQ / Docs
      |                    +---> Vector DB / Search Index
      |
      +---> Prompt Builder / Masking Layer
      |
      +---> LLM Adapter Layer ---> Claude API
      |                       +---> ChatGPT API
      |                       +---> Grok API
      |
      +---> Ticket Service ---> IT Staff / IT Teams Channel
      |
      +---> Internal App DB ---> Knowledge Loop ---> (feeds back to Retrieval)
```

---

## 3. Module Design

### 3.1 Teams Bot Layer

**Functions:**

- Receive user natural language questions
- Display answers
- Display follow-up question cards
- Display ticket creation results
- Display handoff results
- Display ticket status

**Interaction forms:**

- Plain text messages
- Adaptive Cards
- Button options: View suggested steps / Supplement info / Handoff / Check ticket status

**Suggested commands:**

- `I want to report an issue`
- `Help me check an IT problem`
- `Check ticket`
- `Transfer to human`

### 3.2 Internal Gateway (Mac mini)

Core orchestration hub.

**Sub-modules:**

| Module | Responsibility |
|--------|---------------|
| `message_parser` | Parse incoming messages, extract intent |
| `session_manager` | Maintain conversation sessions across messages |
| `user_context_loader` | Load user identity & department context |
| `retrieval_orchestrator` | Coordinate retrieval from multiple sources |
| `prompt_builder` | Assemble prompt with context + masking |
| `policy_guard` | Enforce escalation rules & safety policies |
| `response_router` | Decide: answer / follow-up / create ticket / handoff |
| `logging_service` | Write logs to DB |

### 3.3 Retrieval Layer

Provides grounded content to avoid naked LLM answers.

**Data sources:**

| Source | Origin |
|--------|--------|
| Helpdesk History | Danny's Helpdesk.xlsx |
| SOP / FAQ / Docs | ERP, BPM, Outlook, NAS, Printer, VPN docs |
| Knowledge Items | Closed-case knowledge entries, curated FAQs |

**Retrieval strategy: Hybrid Retrieval**

- Keyword / BM25
- Embedding similarity
- Category / system filtering
- Completed & reusable case boosting

Why not embedding-only: IT issues often contain system names, error codes, permission names, specific keywords that keyword search handles better.

### 3.4 Prompt Builder / Masking Layer

Critical for Cloud LLM architecture.

**Functions:**

- Assemble user question + retrieval results into prompt
- Mask sensitive information
- Control data scope sent to external API
- Add system instructions & answer policy

**Masking targets:**

- Employee ID
- Email addresses
- Attachment real paths
- Personal phone numbers
- Internal hostnames
- Unnecessary account identifiers

**Example:**

- Original: `I'm A1234, Outlook can't receive mail from abc@company.com`
- Masked: `An employee reports Outlook cannot receive mail from a specific external customer`

### 3.5 LLM Adapter Layer

Unified interface, provider-agnostic.

**Methods:**

```
generate_answer(question, context, metadata)
classify_issue(question, context)
decide_followup(question, context)
summarize_ticket(conversation)
augment_knowledge(case_record)
draft_resolution_note(ticket_data)
```

**Providers:**

- `openai_provider.py`
- `anthropic_provider.py`
- `xai_provider.py`

Phase 1: Connect one primary model only. Reserve interfaces for others.

### 3.6 Ticket Service

**Functions:**

- Create ticket
- Save ticket status
- Assign IT staff
- Provide query interface
- Save closure info
- Trigger knowledge writeback

Phase 1: Use internal DB + Teams IT Channel instead of formal ticket system.

### 3.7 Knowledge Loop

Makes the system smarter over time.

**Flow:**

1. IT staff closes ticket
2. System asks if case can be converted to knowledge
3. If yes, AI converts case to standard knowledge entry
4. Write to vector DB & knowledge table
5. Available for future retrieval

---

## 4. Data Design

### 4.1 Original Helpdesk.xlsx Fields

- Start Time
- Completion Time
- User
- WorkID
- System
- Question
- Attachment
- Assignee
- Completion Status
- Completion Date
- Days Incomplete
- Reply
- Email

### 4.2 Standardized `cases` Table

| Field | Description |
|-------|-------------|
| `case_id` | Primary key |
| `source_type` | `excel_history` |
| `source_row_id` | Row reference |
| `created_at` | Timestamp |
| `closed_at` | Timestamp |
| `requester_name` | Name |
| `requester_work_id_masked` | Masked employee ID |
| `requester_email_masked` | Masked email |
| `system_raw` | Original system name |
| `system_normalized` | Standardized system name |
| `question_raw` | Original question |
| `reply_raw` | Original reply |
| `assignee_raw` | Original assignee |
| `status_raw` | Original status |
| `status_normalized` | Standardized status |
| `attachment_meta` | Attachment metadata |
| `is_reusable` | Whether case is reusable for knowledge |
| `quality_score` | Reply quality score |

### 4.3 `knowledge_items` Table

| Field | Description |
|-------|-------------|
| `knowledge_id` | Primary key |
| `source_case_id` | Reference to source case |
| `title` | Knowledge entry title |
| `system` | System category |
| `category` | Issue category |
| `problem_summary` | Summary of the problem |
| `symptoms` | Typical symptoms |
| `possible_causes` | Possible causes |
| `resolution_steps` | Step-by-step resolution |
| `escalation_rule` | When to escalate |
| `keywords` | Search keywords |
| `visibility_scope` | Who can see this |
| `created_by` | Creator |
| `created_at` | Timestamp |
| `embedding_ref` | Vector embedding reference |

### 4.4 `tickets` Table

| Field | Description |
|-------|-------------|
| `ticket_id` | Primary key |
| `requester_id` | Requester reference |
| `title` | Ticket title |
| `summary` | LLM-generated summary |
| `system` | System category |
| `category` | Issue category |
| `priority` | Priority level |
| `status` | Current status |
| `assignee` | Assigned IT staff |
| `source_channel` | Origin channel |
| `created_at` | Timestamp |
| `updated_at` | Timestamp |
| `closed_at` | Timestamp |
| `llm_confidence` | Model confidence score |
| `needs_handoff` | Whether handoff is needed |

### 4.5 `messages` Table

| Field | Description |
|-------|-------------|
| `message_id` | Primary key |
| `ticket_id` | Reference to ticket |
| `sender_type` | user / bot / it_staff |
| `sender_id` | Sender reference |
| `content` | Original content |
| `masked_content` | PII-masked content |
| `timestamp` | Timestamp |

### 4.6 `retrieval_logs` Table

| Field | Description |
|-------|-------------|
| `log_id` | Primary key |
| `ticket_id` | Reference to ticket |
| `query_text` | Search query |
| `retrieved_case_ids` | Matched case IDs |
| `retrieved_doc_ids` | Matched doc IDs |
| `ranking_scores` | Retrieval scores |
| `final_context_size` | Context size sent to LLM |
| `timestamp` | Timestamp |

### 4.7 `feedback` Table

| Field | Description |
|-------|-------------|
| `feedback_id` | Primary key |
| `ticket_id` | Reference to ticket |
| `user_helpful` | Boolean |
| `user_comment` | Optional comment |
| `created_at` | Timestamp |

---

## 5. Helpdesk.xlsx Preprocessing Strategy

### 5.1 Import Pipeline

```
Helpdesk.xlsx
  -> Field mapping
  -> Field cleaning
  -> Status & system normalization
  -> Low-quality reply detection
  -> Create case records
  -> AI augmentation to SOP-style knowledge entries
  -> Vectorization & indexing
```

### 5.2 Normalization Rules

**System names:**

| Raw | Normalized |
|-----|-----------|
| `Outlook` / `outlook` | `Outlook` |
| `印表機` / `列印機` | `Printer` |
| `ERP系統` | `ERP` |

**Status:**

| Raw | Normalized |
|-----|-----------|
| `V`, `v` | `Closed` |
| blank | `Open` or `Unknown` |

**Low-quality reply detection:**

These replies should NOT be used as direct answers — require AI augmentation:

- 已處理
- OK
- 已協助
- 完成
- 請重開機
- 已排除

### 5.3 AI Augmentation

Convert historical records into usable knowledge entries.

**Input:** System, Question, Reply, Assignee, Status

**Output:**

- Problem summary
- Typical symptoms
- Possible causes
- Suggested steps
- Whether self-serviceable
- When to escalate
- Keywords

---

## 6. Answer Strategy

### 6.1 Grounded Answer Policy

- Prioritize retrieval content
- Never fabricate internal procedures
- If info insufficient, ask follow-up questions
- If involves permissions / hardware / account lockout, recommend handoff

### 6.2 Answer Levels

| Level | Condition | Action |
|-------|-----------|--------|
| Level 1: Direct Answer | FAQ, high-similarity historical case, SOP-backed | Answer directly |
| Level 2: Conditional Answer | Need to confirm state, multiple possible causes | Answer with caveats, suggest troubleshooting |
| Level 3: Handoff | Permissions, hardware, data anomalies, low confidence | Create ticket, transfer to IT |

### 6.3 Confidence Strategy

Tracked signals:

- Retrieval score
- Model confidence
- Rule-based escalation flag

**Forced handoff conditions:**

- Insufficient retrieval results
- Hit sensitive category
- User reports answer ineffective repeatedly
- Involves hardware or permissions

---

## 7. Privacy & Security Strategy

### 7.1 Data Handling Principles

- Original Excel & tickets stay in internal DB
- Full attachments never sent to cloud LLM
- Employee IDs, emails, hostnames masked before sending
- Only minimal necessary context sent to LLM API
- API call audit logs retained

### 7.2 Executive Summary

> The system uses a Mac mini as the company's internal AI Gateway, completing data retrieval, masking, and process control first, then sending only minimal necessary context to Claude / ChatGPT / Grok models for answers. This balances internal data control with access to advanced external model capabilities.

---

## 8. API Design

### 8.1 Bot API

**`POST /bot/message`**

```json
// Request
{
  "user_id": "u123",
  "channel": "teams",
  "message": "Outlook can't receive mail",
  "session_id": "s001"
}

// Response
{
  "action": "answer",
  "reply": "Please first check your blocked senders list...",
  "ticket_id": null,
  "followup_questions": []
}
```

### 8.2 Retrieval API

**`POST /retrieve/search`**

```json
{
  "query": "Outlook can't receive external mail",
  "system_hint": "Outlook",
  "top_k": 5
}
```

### 8.3 LLM Task API

- `POST /llm/generate-answer`
- `POST /llm/classify`
- `POST /llm/followup`
- `POST /llm/augment-knowledge`

### 8.4 Ticket API

- `POST /tickets`
- `GET /tickets/{ticket_id}`
- `POST /tickets/{ticket_id}/close`
- `POST /tickets/{ticket_id}/handoff`

### 8.5 Knowledge API

- `POST /knowledge/import-excel`
- `POST /knowledge/augment`
- `POST /knowledge/publish`
- `GET /knowledge/search`

---

## 9. Prompt Design

### 9.1 Answer Prompt

- Only answer based on provided content
- If insufficient info, ask follow-up
- If sensitive issue, recommend handoff
- Use concise, actionable tone

### 9.2 Classification Prompt

Output: `system`, `category`, `priority`, `needs_handoff`, `confidence`

### 9.3 Knowledge Augmentation Prompt

Output: problem summary, symptoms, causes, resolution steps, escalation conditions, keywords

### 9.4 Ticket Summarization Prompt

Output: title, summary, affected_system, symptoms, user_actions_taken, recommended_next_step

---

## 10. Scenario Validation

### Scenario 1: High-frequency Simple Question — "Outlook can't receive external mail"

**Expected path: Level 1 Direct Answer**

```
Employee asks in Teams: "My Outlook can't receive customer emails"
  -> Teams Bot -> Gateway receives message
  -> session_manager creates/continues session
  -> user_context_loader pulls employee context
  -> Retrieval Layer: BM25 + embedding search
     -> Hits 15 similar cases + 1 SOP
  -> Prompt Builder: mask employee ID/email, assemble top 3 cases + SOP
  -> LLM Adapter -> Claude API
  -> Claude returns: "Please check: 1. Junk folder 2. Blocked senders 3. Transport Rules..."
  -> Write log -> Return to Teams Bot
  -> Bot shows answer + buttons: "Helpful / Not helpful / Transfer to human"
```

**Result: PASS**

**Gap identified:** `user_context_loader` needs employee department/device info. Phase 1 data source unclear — no AD integration available.

**Recommendation:** Phase 1 use only Teams-provided identity (name, email). `user_context_loader` starts as stub.

### Scenario 2: Insufficient Info — "ERP is broken"

**Expected path: Follow-up questions**

```
Employee: "ERP is broken"
  -> Retrieval: search "ERP broken" -> too many scattered results
  -> LLM (classify + followup): needs_followup = true
  -> Bot shows Adaptive Card:
     - Text field: "Please describe the error"
     - Quick buttons: "Login issue" / "Report issue" / "Permission issue" / "Other"
  -> Employee clicks "Login issue"
  -> Re-run Retrieval + LLM with refined context
  -> Hit "ERP login failure -> clear cookie + reset password" case
  -> Answer
```

**Result: PASS**

**Gaps identified:**

1. How many follow-up rounds before stopping? If employee stays vague after 3 rounds?
2. Where do Adaptive Card quick-button options come from? LLM-generated or preset?

**Recommendations:**

- Set `max_followup_rounds = 2`, then force handoff
- Quick buttons: LLM-generated from retrieval result categories, with fallback presets

### Scenario 3: Must Handoff — "Laptop keeps blue-screening"

**Expected path: Level 3 Handoff**

```
Employee: "My laptop keeps blue-screening"
  -> Retrieval: found cases, all resolved by "replaced" / "sent for repair"
  -> LLM (classify): category=Hardware, needs_handoff=true, confidence=low
  -> policy_guard confirms: Hardware -> must handoff
  -> Ticket Service: create ticket
     title: "Laptop repeated BSOD"
     summary: LLM-generated
     priority: High
     similar_cases: [historical case IDs]
  -> Teams IT Channel: send notification card
     IT sees: summary + employee info + similar cases
  -> Bot replies: "Ticket #TK-0042 created, IT will contact you soon"
```

**Result: PASS**

**Gap identified:** `policy_guard` rules depend on LLM classification. If LLM misclassifies?

**Recommendation:** policy_guard uses **dual-layer judgment**:

1. **Rule-based keywords**: BSOD, hard drive, screen broken, won't boot -> force handoff
2. **LLM classification** as supplement

### Scenario 4: Check Ticket — "Is my printer issue fixed?"

**Expected path: Ticket query**

```
Employee: "Check ticket" or "Is my printer issue fixed?"
  -> message_parser: intent = ticket_query
  -> Ticket Service: query open tickets by user_id
     Found #TK-0038 "Printer cannot print" status: In Progress
  -> Bot shows Adaptive Card:
     Ticket #TK-0038
     Status: In Progress
     Assignee: Danny
     Last updated: 2026-03-11
     [Buttons: Remind / Add info]
```

**Result: PASS**

**Gap identified:** How does `message_parser` distinguish "check ticket" vs "new question"? If employee says "printer still can't print" — is it checking old ticket or reporting new issue?

**Recommendation:**

- message_parser uses intent classification (LLM or rule-based)
- If open ticket exists with high similarity, ask: "Are you asking about ticket #TK-0038 progress?"

### Scenario 5: Knowledge Loop — IT Closes Case

```
Danny closes #TK-0038 in IT Channel
  -> Ticket Service triggers knowledge loop
  -> LLM (augment_knowledge):
     Input: full conversation + closure notes
     Output:
       title: "HP LaserJet print failure - driver conflict"
       symptoms: ["Print queue stuck", "Driver shows error"]
       resolution_steps: ["Remove old driver", "Install v3.2.1", "Restart spooler"]
       keywords: ["printer", "HP", "driver", "spooler"]
  -> Bot DMs Danny:
     "Knowledge entry generated. Confirm publish?"
     [Preview card + Edit / Confirm / Reject]
  -> Danny confirms -> write to knowledge_items + vectorize
```

**Result: PASS**

**Practical gaps:**

1. How does Danny close a case? Type in Teams Channel? Or a form?
2. Phase 1 without formal ticket system — what triggers "closure"?

**Recommendation:** Phase 1 use Adaptive Card with a close button in IT Channel. Danny clicks "Close" -> fills closure notes -> triggers loop.

### Validation Summary

| Aspect | Status | Notes |
|--------|--------|-------|
| High-frequency Q&A | PASS | RAG + LLM core path works |
| Follow-up questions | PASS | Need max rounds limit |
| Handoff to human | PASS | policy_guard needs dual-layer judgment |
| Check ticket | PASS | Need intent classification |
| Knowledge writeback | PASS | Need to define closure trigger |
| PII masking | PASS | Need masking rule maintenance plan |
| LLM adapter switching | N/A for Phase 1 | Connect one provider, reserve interface |

---

## 11. Architecture Gaps Identified

### Gap 1: Intent Router Not Elevated

`message_parser` is currently a sub-module, but it needs to do intent classification (new question / check ticket / handoff / chitchat). Should be promoted to the **first decision node** in Gateway.

**Recommendation:** Elevate to `intent_router` as a top-level Gateway component before all other processing.

### Gap 2: Session / Multi-turn Storage Strategy Undefined

`session_manager` is mentioned but not designed. Follow-up scenarios need cross-message context.

**Needs definition:**

- Session timeout duration
- Storage location (memory? DB?)
- Context window limit (how many past messages to include)
- Session cleanup policy

### Gap 3: Error Handling / Degradation Strategy

If Claude API is down, or Retrieval returns zero results, what does Bot say?

**Recommendation:** Add `fallback_handler`:

- API failure -> direct handoff + notify Danny
- Zero retrieval results -> answer with disclaimer + offer handoff
- Timeout -> apologize + suggest retry or handoff

---

## 12. OpenClaw Evaluation

### What is OpenClaw

[OpenClaw](https://openclaw.ai) is an **open-source personal AI assistant platform**:

- Integrates with multiple chat platforms (WhatsApp, Telegram, Discord, Slack, **Teams**)
- Local deployment, privacy-first
- Can execute system operations (file read/write, shell commands, web browsing)
- Persistent memory + extensible skill/plugin system
- Supports Anthropic, OpenAI, or local models

### Teams Support

OpenClaw supports Microsoft Teams via plugin (`@openclaw/msteams`):

- Supports DM, group chat, team channels
- Supports text messages, DM file attachments, Adaptive Cards
- Requires Azure Bot setup (App ID, password, tenant ID)

**Known limitations:**

| Limitation | Detail |
|-----------|--------|
| Message history | Requires Microsoft Graph permissions |
| Channel files | Requires SharePoint site ID + Graph permissions |
| Private channels | Limited bot support |
| Markdown | Teams markdown more limited than Slack/Discord |
| Timeout | Long processing time may cause duplicate or lost replies |

### Overlap Analysis with Our Architecture

| Capability We Need | Our Architecture | OpenClaw Provides | Overlap? |
|---|---|---|---|
| Teams integration | Teams Bot (self-built) | Teams plugin | YES - can save effort |
| Session management | session_manager | Persistent memory | PARTIAL overlap |
| Intent routing | message_parser (domain-specific) | No built-in | NO - must build |
| RAG / Retrieval | Retrieval Layer (self-built) | No built-in RAG | NO - must build |
| PII Masking | Prompt Builder / Masking | No built-in masking | NO - must build |
| LLM calls | LLM Adapter Layer | Supports Anthropic/OpenAI | YES - can save effort |
| Ticket system | Ticket Service (self-built) | No built-in | NO - must build |
| Knowledge Loop | Knowledge Loop (self-built) | No built-in | NO - must build |

### Option A: Build Everything Ourselves (Current Plan)

```
Teams Bot (self-built) -> Gateway (self-built) -> RAG + LLM + Ticket
```

- Full control
- More development work
- No third-party framework dependency

### Option B: OpenClaw as Communication + LLM Base Layer

```
OpenClaw (Teams plugin + LLM calls) -> Our skill plugins (RAG + Masking + Ticket)
```

- Save Teams integration + LLM adapter work
- Use OpenClaw's plugin/skill mechanism to mount business logic
- Core value (RAG, masking, ticket, knowledge loop) still self-built

### Risks of Using OpenClaw

1. **Timeout risk** — OpenClaw docs explicitly mention Teams timeout causing lost replies. Our RAG + LLM chain is inherently slow.
2. **Adaptive Cards depth** — How complex can our follow-up/closure cards be?
3. **Masking layer insertion point** — If OpenClaw sends user messages to LLM directly, can our Masking Layer intercept before LLM call? Must verify plugin architecture allows pre-LLM interception.

### Verdict

**Phase 1: Do NOT introduce OpenClaw.** Build ourselves.

Reasons:

- Core value modules (RAG, masking, ticket, knowledge loop) all need to be self-built regardless
- OpenClaw only saves Teams integration + LLM adapter — the simpler parts
- Timeout risk in Teams plugin is a concern for our slow RAG+LLM pipeline
- Introducing a framework adds learning curve and dependency for limited payoff

**Phase 4+: Re-evaluate OpenClaw** when:

- Expanding to channels beyond Teams (LINE, Slack)
- Adding system automation (shell commands, script execution)
- Needing agent-style autonomous task execution

### Open Question (Unresolved)

> Can OpenClaw's skill plugin architecture allow pre-LLM interception for RAG injection and PII masking?

This is the key question. If yes, Option B becomes more viable. If no, OpenClaw is only useful as a thin communication layer. Needs further investigation of OpenClaw's plugin development docs.

---

## 13. Development Phases

### Phase 0: Data Validation

- Import Helpdesk.xlsx
- Clean fields
- Initial category normalization
- Validate usable data ratio
- Generate first-version knowledge JSON

### Phase 1: Answerable Teams Bot

- Teams Bot basic entry point
- Gateway basic version
- Retrieval MVP
- Single LLM provider
- Answer / follow-up / handoff

### Phase 2: Ticket & Feedback

- Ticket DB
- IT channel notifications
- Ticket query
- Helpful / unhelpful feedback
- Retrieval logs

### Phase 3: Knowledge Loop

- Post-closure knowledge conversion
- Human confirmation for publishing
- Continuous vector DB updates
- High-frequency FAQ extraction

### Phase 4: Advanced Capabilities

- Multi-provider switching
- Cost control
- Answer quality evaluation
- Department dashboard
- Potential Webview / artifact extensions
- Re-evaluate OpenClaw for multi-channel / automation

---

## 14. Value Proposition

### For Danny (IT Staff)

- No need to manually write extensive FAQs
- Directly use historical Helpdesk as cold-start knowledge
- Bot pre-filters and triages issues
- Reduces burden of repeatedly answering high-frequency questions

### For IT Manager

- No need to maintain local large models
- Leverage strongest commercial model capabilities
- Internal gateway control & data masking preserved
- Logs, handoff, knowledge writeback — risk controllable

### For Company

- Improve IT support efficiency
- Retain company's own case memory
- Build an evolving IT knowledge platform
