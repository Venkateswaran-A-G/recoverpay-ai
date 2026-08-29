# PROMPT_LOG.md - Master AI Prompt & Action Journal

This file records every prompt given to Cursor Pro, the files generated/edited, and the exact actions executed for complete transparency and proof of build.

---

### [Prompt #01] - Setup & Database Models Initialization
- **Timestamp**: Phase 1 Initialization
- **Exact User Prompt**: "Hello! Read @AGENTS.md and @technical_design_doc.md first. Please set up our Python virtual environment, create a .env file for API keys, install dependencies (fastapi, uvicorn, sqlalchemy, pydantic, email-validator, razorpay, openai, pytest, httpx), and build our database models in backend/database.py and schemas in backend/schemas.py. Then commit all changes with message 'feat: initial database models and schemas' and push to main."
- **Files Created / Modified**:
  - `backend/database.py` (SQLAlchemy ORM models: Transaction, AuditLog, OptOutRegistry)
  - `backend/schemas.py` (Pydantic v2 schemas: RazorpayFailurePayload, LLMDiagnosticOutput, GuardrailEvaluationResult)
  - `requirements.txt`
  - `.env`
- **Actions Executed**: Installed Python dependencies, initialized SQLite database tables, ran `git commit` and `git push origin main`.

### [Prompt #02] - Verify and fix requirements encoding + ORM location
- **Timestamp**: 2026-08-29 / Phase 2 fix
- **Exact User Prompt**: "Verify these issues exist and fix them: Bug 1: The requirements.txt file contains encoding corruption where spaces have been inserted between every character... Bug 2: The database ORM models are defined in backend/database.py, but AGENTS.md specifies backend/models.py..."
- **Files Created / Modified**:
  - `requirements.txt` (regenerated UTF-8, no UTF-16 NULs)
  - `backend/models.py` (new — Transaction, AuditLog, OptOutRegistry, Base)
  - `backend/database.py` (engine / session / init_db only; re-exports models)
  - `backend/schemas.py` (docstring points at models.py)
  - `tests/test_database.py` (imports from backend.models)
  - `BUILD_LOG.md` (Entry #04)
- **Actions Executed**: Confirmed UTF-16 LE BOM on requirements.txt; moved ORM to models.py; regenerated requirements as UTF-8; ran pytest; committed and pushed to main.

### [Prompt #03] - Financial guardrails state machine
- **Timestamp**: 2026-08-29 / Phase 3
- **Exact User Prompt**: "Hello! Read @AGENTS.md and @technical_design_doc.md first. Please create backend/guardrails.py to evaluate transaction safety rules independently of LLMs (amount cap > ₹5,000, max 2 retries, and opt-out registry check). Then create tests/test_guardrails.py covering all 4 guardrail test cases using pytest and an in-memory database. Run pytest in terminal to verify all tests pass. Log this prompt in @PROMPT_LOG.md and any issue in @BUILD_LOG.md. Finally, git commit with message 'feat: implement financial guardrails state machine and pytest suite' and push to main."
- **Files Created / Modified**:
  - `backend/guardrails.py` (opt-out, retry cap, amount threshold)
  - `tests/test_guardrails.py` (4 in-memory SQLite cases)
  - `PROMPT_LOG.md`
  - `BUILD_LOG.md`
- **Actions Executed**: Implemented deterministic `evaluate_guardrails()`. Pytest: 4 passed in `tests/test_guardrails.py`, 14 passed overall. Committed and pushed to main.

### [Prompt #04] - Regional multi-lingual LLM diagnostic agent
- **Timestamp**: 2026-08-29 / Phase 4
- **Exact User Prompt**: "Hello! Read @AGENTS.md and @ai_design_doc.md first. Please create backend/agent.py using OpenAI GPT-4o-mini with structured JSON parsing to diagnose payment failure codes and generate localized WhatsApp recovery messages in the customer's native regional language based on location/state: Karnataka -> Kannada/English; Tamil Nadu -> Tanglish / Tamil; Telangana / AP -> Telugu / English; Maharashtra -> Marathi / Hinglish; Delhi / North -> Hinglish; Default / Preference -> Simple English. Ensure output is validated via LLMDiagnosticOutput Pydantic schema and preserves the Razorpay Payment Link. Include a deterministic fallback mechanism using pre-defined regional templates if the API call fails or key is missing. Log this prompt in @PROMPT_LOG.md and any issue in @BUILD_LOG.md. Finally, git commit with message 'feat: implement regional multi-lingual LLM diagnostic agent with fallback templates' and push to main."
- **Files Created / Modified**:
  - `backend/agent.py` (GPT-4o-mini JSON mode, locale router, link check, regional fallbacks)
  - `backend/schemas.py` (`LanguageRegister`, `RecoveryCopyRequest`, `language_register` on `LLMDiagnosticOutput`)
  - `tests/test_agent.py`
  - `PROMPT_LOG.md`
  - `BUILD_LOG.md`
- **Actions Executed**: Implemented diagnose_failure() with schema + exact rzp.io link gate. Fallback when TEST_MODE, missing key, low confidence, or bad JSON. Ran pytest. Committed and pushed to main.

### [Prompt #05] - FastAPI webhook engine, metrics, and batch simulator
- **Timestamp**: 2026-08-29 / Phase 5
- **Exact User Prompt**: "Hello! Read @AGENTS.md, @technical_design_doc.md, and @ai_design_doc.md first. Please build backend/main.py implementing all FastAPI endpoints specified in technical_design_doc.md: Razorpay Webhook Ingestion (POST /api/v1/webhooks/razorpay) with HMAC SHA256... Dashboard Metrics... Transactions Route... Audit Logs... Manual Approval... Batch Simulator... Test backend/main.py using uvicorn. Log this prompt in @PROMPT_LOG.md and any issue in @BUILD_LOG.md. Finally, git commit with message 'feat: implement FastAPI webhook engine with multi-lingual regional recovery, audit logging, and batch simulator' and push to main."
- **Files Created / Modified**:
  - `backend/main.py` (all FastAPI routes + recovery pipeline)
  - `backend/razorpay_client.py` (HMAC SHA256 + TEST_MODE payment links)
  - `backend/models.py` / `backend/database.py` (`customer_state` + SQLite ALTER)
  - `backend/schemas.py` (API response models)
  - `tests/test_main.py`
  - `scripts/smoke_api.py`
  - `PROMPT_LOG.md`, `BUILD_LOG.md`
- **Actions Executed**: Pytest 29 passed. Uvicorn smoke: health 200, batch 10, invalid HMAC 401, Tamil Nadu webhook 202 + Tanglish dispatch, PII-masked transactions, audit graph. Committed and pushed to main.

### [Prompt #06] - RazorpayX / Stripe / Linear dashboard UI
- **Timestamp**: 2026-08-29 / Phase 6
- **Exact User Prompt**: "Hello! Read @AGENTS.md, @technical_design_doc.md, and @pitch_and_interview_defense.md first. Please build frontend/index.html (mounted on FastAPI at GET /) styled like a blend of RazorpayX Merchant Portal + Stripe Dashboard + Linear.app: RazorpayX theme & header, Stripe-style metric cards, Wise/Revolut regional transaction stream, high-value guardrail highlight, Linear-style visual audit execution drawer. Test by running uvicorn backend.main:app --reload and opening http://localhost:8000. Log this prompt in @PROMPT_LOG.md and any issue in @BUILD_LOG.md. Finally, git commit with message 'feat: implement RazorpayX and Stripe inspired fintech dashboard UI with multi-lingual badges' and push to main."
- **Files Created / Modified**:
  - `frontend/index.html`
  - `backend/main.py` (GET `/` FileResponse, `/health` includes `test_mode`)
  - `tests/test_main.py`
  - `PROMPT_LOG.md`, `BUILD_LOG.md`
- **Actions Executed**: Mounted dashboard at `/`. Pytest + uvicorn HTML/API smoke. Committed and pushed to main.

### [Prompt #07] - 3D glassmorphism dashboard restyle
- **Timestamp**: 2026-08-29 / Phase 6 UI polish
- **Exact User Prompt**: "Hello! Read @AGENTS.md, @technical_design_doc.md, and @pitch_and_interview_defense.md first. Please build frontend/index.html (mounted on FastAPI at GET /) styled like a 3D Glassmorphism RazorpayX + Stripe Fintech Dashboard: 3D glass cards, RazorpayX header, amber shield banner, regional badges, visual audit drawer. Test by running uvicorn... commit 'feat: implement 3D glassmorphism fintech dashboard UI with multi-lingual badges' and push to main."
- **Files Created / Modified**:
  - `frontend/index.html` (glass panels, ambient orbs, hover lift, amber shield)
  - `tests/test_main.py` (asserts #080a0f, Net Outreach ROI, Amber Shield)
  - `PROMPT_LOG.md`, `BUILD_LOG.md`
- **Actions Executed**: Restyled dashboard. Pytest + uvicorn HTML smoke. Committed and pushed to main.

### [Prompt #08] - Light / Dark glassmorphism toggle
- **Timestamp**: 2026-08-29 / Phase 6 theme
- **Exact User Prompt**: "Please build frontend/index.html ... WITH Light & Dark Mode Toggle: Tailwind darkMode class, Theme Toggle Switch (☀️ Light / 🌙 Dark), localStorage, dark slate #080a0f vs light #f8fafc... commit 'feat: implement 3D glassmorphism fintech dashboard UI with Light and Dark mode toggle and multi-lingual badges' and push to main."
- **Files Created / Modified**:
  - `frontend/index.html` (class darkMode, theme toggle, dual glass tokens)
  - `tests/test_main.py`
  - `PROMPT_LOG.md`, `BUILD_LOG.md`
- **Actions Executed**: Added header toggle + localStorage. Pytest + HTML smoke on :8000. Committed and pushed to main.

### [Prompt #09] - Search and multi-filter toolbar
- **Timestamp**: 2026-08-29 / Phase 6 filters
- **Exact User Prompt**: "Please build frontend/index.html ... WITH Search & Multi-Filter Control Toolbar: live search, amount range, status pills, regional pills, Light/Dark toggle... commit 'feat: implement 3D glassmorphism fintech dashboard UI with search bar, multi-filters, Light/Dark mode, and multi-lingual badges' and push to main."
- **Files Created / Modified**:
  - `frontend/index.html` (toolbar + combined client-side filters)
  - `tests/test_main.py`
  - `PROMPT_LOG.md`, `BUILD_LOG.md`
- **Actions Executed**: Filters AND together on name/phone/payment ID, amount bands, status, and region. Pytest + HTML smoke. Committed and pushed to main.

---
*(Future prompts and file modifications will be appended automatically by Cursor Pro)*
