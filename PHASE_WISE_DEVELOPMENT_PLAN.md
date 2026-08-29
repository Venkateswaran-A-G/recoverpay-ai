# RecoverPay AI — Phase-Wise Development & Implementation Plan

**Project Title**: RecoverPay AI  
**Track**: Track 03 — AI Revenue Recovery  
**Target Event**: Razorpay AI Buildathon 2026  
**Role Target**: AI Builder Intern (₹75,000 / month, Bangalore HQ)  
**IDE Target**: Cursor Pro (Composer Agent Mode with Claude 3.5 Sonnet)  

---

## 🗺️ Master Sprint Roadmap Overview

This phase-wise plan breaks down the entire project into **6 manageable, sequential phases**. Each phase contains:
- **Objective & Deliverables**
- **Exact Prompt to Give Cursor Pro**
- **Verification & Test Checkpoints**
- **Expected Outcome**

```
+-----------------------------------------------------------------------------------+
|                        PHASE-WISE IMPLEMENTATION FLOW                             |
|                                                                                   |
|  [ Phase 1: Environment & Project Setup ] ➔ [ Phase 2: Database & Core Schemas ] |
|                                                                                   |
|  [ Phase 3: Financial Guardrails Engine ]  ➔ [ Phase 4: LLM Agent & Razorpay SDK ]|
|                                                                                   |
|  [ Phase 5: FastAPI Webhooks & Simulator ] ➔ [ Phase 6: Next.js UI & Pitch Demo ] |
+-----------------------------------------------------------------------------------+
```

---

## 📍 Phase 1: Repository Initialization & Workspace Rules

### Objective:
Set up the workspace folder structure, Git repository, environment variables, and feed Cursor Pro its master system rules.

### Tasks:
1. Initialize folder structure:
   ```
   /recoverpay-ai
   ├── AGENTS.md
   ├── BUILD_LOG.md
   ├── .env.example
   ├── backend/
   ├── frontend/
   └── tests/
   ```
2. Place `@AGENTS.md` in the project root folder.
3. Set up `.env` with placeholder environment variables:
   ```env
   OPENAI_API_KEY="sk-proj-..."
   RAZORPAY_KEY_ID="rzp_test_..."
   RAZORPAY_KEY_SECRET="test_secret_..."
   RAZORPAY_WEBHOOK_SECRET="demo_secret_12345"
   DATABASE_URL="sqlite:///./recoverpay.db"
   ```

### Cursor Pro Prompt (Phase 1):
> `@AGENTS.md Please initialize a Python 3.11 virtual environment and install the initial dependencies: fastapi, uvicorn, sqlalchemy, pydantic, email-validator, razorpay, openai, pytest, httpx. Verify that all imports work without errors.`

### Verification Checkpoint:
- Run `python -c "import fastapi, sqlalchemy, pydantic, razorpay; print('Imports OK')"` in terminal.

---

## 📍 Phase 2: Database Models & Pydantic Schemas

### Objective:
Build the database tables (SQLite / PostgreSQL ready) and strict Pydantic v2 schemas for request validation.

### Tasks:
1. Create `backend/database.py`:
   - `Transaction` table (`id`, `amount`, `failure_code`, `recovery_status`, `retry_count`, `created_at`).
   - `AuditLog` table (`id`, `transaction_id`, `step_name`, `step_status`, `llm_prompt`, `guardrail_evaluation`).
   - `OptOutRegistry` table (`phone_number`, `opt_out_source`).
2. Create `backend/schemas.py`:
   - `RazorpayFailurePayload` (Incoming webhook schema).
   - `LLMDiagnosticOutput` (Typed JSON output from GPT-4o-mini).
   - `GuardrailEvaluationResult` (Safety state machine result).
   - `DashboardMetrics` (Aggregate metrics schema).

### Cursor Pro Prompt (Phase 2):
> `@AGENTS.md @technical_design_doc.md Create backend/database.py and backend/schemas.py based on our technical design document specifications. Use SQLAlchemy for ORM models and Pydantic v2 with ConfigDict(from_attributes=True) for API schemas. Include a function init_db() to create tables.`

### Verification Checkpoint:
- Run `python -c "from backend.database import init_db; init_db(); print('DB Created')"` in terminal.
- Verify `recoverpay.db` SQLite database file is created.

---

## 📍 Phase 3: Financial Guardrails Engine & Unit Tests

### Objective:
Build the deterministic non-LLM safety state machine (`backend/guardrails.py`) and write comprehensive unit tests (`tests/test_guardrails.py`).

### Tasks:
1. Implement `backend/guardrails.py`:
   - Check Opt-Out Registry (`opt_out_registry`).
   - Check Retry Count Cap (`retry_count >= 2` ➔ Reject).
   - Check Amount Threshold Cap (`amount > ₹5,000` ➔ Require Human Approval).
2. Create `tests/test_guardrails.py`:
   - Test standard amounts (< ₹5,000) ➔ Pass.
   - Test high-value amounts (> ₹5,000) ➔ Flag for approval.
   - Test retry limit exceeded (2 retries) ➔ Reject.
   - Test opted-out customer phone number ➔ Reject.

### Cursor Pro Prompt (Phase 3):
> `@AGENTS.md Write backend/guardrails.py to evaluate transaction safety rules independently of LLMs. Then write unit tests in tests/test_guardrails.py covering all 4 guardrail scenarios using pytest and an in-memory SQLite database. Run pytest and ensure all tests pass.`

### Verification Checkpoint:
- Run `pytest tests/test_guardrails.py` in terminal.
- Expected Result: `4 passed in <0.5s`.

---

## 📍 Phase 4: LLM Diagnostic Agent & Razorpay SDK Integration

### Objective:
Build `backend/agent.py` to parse payment failure codes using OpenAI GPT-4o-mini and format Hinglish WhatsApp recovery copy with fallback template protection.

### Tasks:
1. Implement `backend/agent.py`:
   - Prompt GPT-4o-mini with failure code, customer first name, and amount.
   - Validate response using `LLMDiagnosticOutput` Pydantic model.
   - Verify payment link preservation in generated copy.
   - Implement deterministic fallback templates if OpenAI API is missing/fails.

### Cursor Pro Prompt (Phase 4):
> `@AGENTS.md @ai_design_doc.md Implement backend/agent.py using OpenAI GPT-4o-mini with structured JSON mode. Parse payment failure payloads into diagnostic summaries and Hinglish WhatsApp copy containing the Razorpay Payment Link. Add a fallback mechanism using pre-defined templates if the API call fails or env key is missing.`

### Verification Checkpoint:
- Test running `backend/agent.py` standalone with test data; verify valid Hinglish output and fallback behavior.

---

## 📍 Phase 5: FastAPI Webhook Ingestion & Simulation Endpoints

### Objective:
Build the core FastAPI web service in `backend/main.py` uniting HMAC authentication, webhook processing, audit logging, dashboard metrics, and batch simulation.

### Tasks:
1. `POST /api/v1/webhooks/razorpay`:
   - HMAC SHA256 signature verification (`X-Razorpay-Signature`).
   - Ingest payload ➔ Evaluate Guardrails ➔ Generate Payment Link ➔ Run LLM Copy Generator ➔ Save Audit Logs.
2. `GET /api/v1/dashboard/metrics`:
   - Aggregate metrics (*Total Failed Volume*, *Recovered Revenue*, *Recovery Rate %*, *Outreach Cost*, *Net ROI*).
3. `POST /api/v1/guardrails/approve/{id}`:
   - Endpoint for merchants to manually approve high-value transactions (> ₹5,000).
4. `POST /api/v1/simulator/run-batch`:
   - Generates 20–100 mock payment failure transactions for demo testing.

### Cursor Pro Prompt (Phase 5):
> `@AGENTS.md @technical_design_doc.md Build backend/main.py creating all FastAPI endpoints specified in technical_design_doc.md. Include HMAC SHA256 verification, step-by-step audit logging into the AuditLog table, metrics calculations, manual approval route, and batch simulator endpoint. Start uvicorn server and test with curl.`

### Verification Checkpoint:
- Run `uvicorn backend.main:app --reload`.
- Test `curl -X POST "http://localhost:8000/api/v1/simulator/run-batch?count=10"`.
- Test `curl "http://localhost:8000/api/v1/dashboard/metrics"`.

---

## 📍 Phase 6: Frontend UI Dashboard & Pitch Video Recording

### Objective:
Build the modern, responsive React/Next.js dashboard UI, visual audit trace graph, and record the 5-minute Loom pitch video.

### Tasks:
1. Build Frontend Dashboard (`frontend/index.html` or Next.js App Router):
   - Metric Summary Cards (Failed Volume, Recovered Amount, Rate %, ROI).
   - Live Webhook Failure Table with "🚨 FLAGGED (>₹5K)" highlight badges and "Approve & Send" buttons.
   - Interactive Audit Drawer displaying visual execution node traces per transaction.
2. Run Batch Simulation (100 Transactions):
   - Verify metrics populate accurately.
3. Record 5-Minute Pitch Video:
   - Follow the exact video storyboard in `pitch_and_interview_defense.md`.

### Cursor Pro Prompt (Phase 6):
> `@AGENTS.md @pitch_and_interview_defense.md Create the frontend UI dashboard connecting to our FastAPI endpoints. Display summary metric cards, transaction table with guardrail flag badges, and an interactive audit log drawer showing execution step traces. Style cleanly using Tailwind CSS.`

### Verification Checkpoint:
- Open dashboard in browser, click *"Simulate 20 Failed Payments"*, inspect audit trace for a flagged >₹5K transaction, click *"Approve & Send"*, and confirm metrics update.

---

## 📑 Summary Phase Checklist

| Phase | Core Milestone | Key Deliverable | Status |
| :---: | :--- | :--- | :---: |
| **Phase 1** | Workspace & Rules Setup | `AGENTS.md`, `.env`, Virtualenv | ✅ Complete |
| **Phase 2** | Database & Schemas | `database.py`, `schemas.py` | ✅ Complete |
| **Phase 3** | Guardrails Engine & Tests | `guardrails.py`, `tests/test_guardrails.py` | ✅ Complete |
| **Phase 4** | LLM Agent & Copy Generator | `agent.py` (GPT-4o-mini + Fallbacks) | ✅ Complete |
| **Phase 5** | FastAPI Webhooks & Simulator | `main.py` (Webhooks, Metrics, Batch Simulator) | ✅ Complete |
| **Phase 6** | Dashboard UI & Pitch Video | `frontend/index.html`, 5-Min Video Script | ✅ Complete (pitch video is a submission artifact) |

---

*Master Phase-Wise Development Plan complete for RecoverPay AI — Razorpay AI Buildathon 2026.*
