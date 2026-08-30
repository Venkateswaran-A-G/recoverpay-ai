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

### [Prompt #10] - Verify suite and mark MVP 100% complete
- **Timestamp**: 2026-08-29 / Final verification
- **Exact User Prompt**: "Hello! Read @AGENTS.md and @engineering_testing_plan.md first. Please run pytest tests/test_guardrails.py in terminal to verify all financial guardrail assertions pass with zero warnings. Verify that uvicorn backend.main:app is running cleanly. Update @BUILD_LOG.md and @PROMPT_LOG.md marking the project build 100% complete and verified. Finally, git commit with message 'docs: verify buildathon codebase, test suite, and mark MVP 100% complete' and push to main."
- **Files Created / Modified**:
  - `tests/test_guardrails.py` (dispose in-memory SQLite engine to clear ResourceWarning)
  - `PHASE_WISE_DEVELOPMENT_PLAN.md` (all 6 phases marked complete)
  - `BUILD_LOG.md` (Entry #12 — MVP 100% verified)
  - `PROMPT_LOG.md`
- **Actions Executed**: `pytest tests/test_guardrails.py -W error` → 4 passed, 0 warnings. `GET /health` on running uvicorn → 200 `{status: ok, test_mode: true}`. Committed and pushed to main.

### [Prompt #11] - Fix simulate button error handling
- **Timestamp**: 2026-08-29 / Dashboard bugfix
- **Exact User Prompt**: "Verify these issues exist and fix them: Bug 1: The simulate button click handler calls fetch() and immediately parses the response with res.json() without checking the HTTP status code first..."
- **Files Created / Modified**:
  - `frontend/index.html` (simulate handler checks `res.ok` like approve)
  - `tests/test_main.py`
  - `PROMPT_LOG.md`, `BUILD_LOG.md`
- **Actions Executed**: Confirmed missing `res.ok` on simulate. Error toasts now use FastAPI `detail` / status instead of `undefined` counts.

---
*(Future prompts and file modifications will be appended automatically by Cursor Pro)*

---

### [Prompt #20] - Live India Downstream Bank Outage Map
- **Timestamp**: 2026-08-30 / Bank health monitoring feature
- **Exact User Prompt**: "Implement Live India Downstream Bank Outage Map: bank health endpoint, failure rate detection, BANK_OUTAGE_HOLD status, bank outage note in WhatsApp, 3D glassmorphism bank health banner."
- **Files Created / Modified**:
  - `backend/schemas.py` (added `BANK_OUTAGE_HOLD`, `RETRY_SCHEDULED_POST_BANK_RECOVERY` to `RecoveryStatus`)
  - `backend/main.py` (added `_BANK_KEYWORDS`, `_BANK_OUTAGE_OVERRIDES`, `SIM_FAILURE_REASONS`, `detect_bank()`, `compute_bank_health()`; bank outage hold check in `process_failure_event()`; `GET /api/v1/bank-health`; `POST /api/v1/simulator/bank-outage`)
  - `backend/agent.py` (`build_rich_whatsapp_message()` accepts `bank_outage_note` parameter)
  - `frontend/index.html` (bank health banner with live status pills, "Simulate SBI Outage" button, `BANK_OUTAGE_HOLD` filter chip, `loadBankHealth()` JS)
  - `PROMPT_LOG.md`
- **Actions Executed**: `GET /api/v1/bank-health` verified → all 5 banks operational. `pytest` → 30 passed. Committed and pushed.

---

### [Prompt #19] - Rich structured Green API WhatsApp messages
- **Timestamp**: 2026-08-30 / Green API message formatting
- **Exact User Prompt**: "Verify and update backend/agent.py so that every WhatsApp message sent via Green API explicitly formats and includes: plain failure cause, actionable fix tip, regional dialect, 1-click Razorpay link."
- **Files Created / Modified**:
  - `backend/agent.py` (added `_GREETINGS`, `_POSSESSIVES`, `_CAUSE_PHRASES`, `_ACTION_TIPS` dicts; added `build_rich_whatsapp_message()` function producing exact 3-line format)
  - `backend/main.py` (imported `build_rich_whatsapp_message`; Green API send now uses `build_rich_whatsapp_message(request, register)` instead of `diagnostic.hinglish_message`)
  - `PROMPT_LOG.md`
- **Actions Executed**: All 5 dialects (Kanglish/Tanglish/Telugu/Marathi/Hinglish) verified via preview test. Live send `idMessage=3EB02C005FCB72B9F90A10` delivered. `pytest` → 30 passed. Committed and pushed.

---

### [Prompt #18] - Green API WhatsApp Integration
- **Timestamp**: 2026-08-30 / Green API live messaging
- **Exact User Prompt**: "Please integrate Green API into backend/agent.py. Add send_green_api_message(). In backend/main.py, whenever a webhook payment failure is processed or simulation runs, call send_green_api_message to send the regional recovery message to MY_PERSONAL_WHATSAPP."
- **Files Created / Modified**:
  - `backend/agent.py` (added `send_green_api_message()` — POST to `api.green-api.com/waInstance{ID}/sendMessage/{TOKEN}`)
  - `backend/main.py` (imported `send_green_api_message`; called after DB commit in `dispatch_recovery()`)
  - `.env` (added `GREEN_API_INSTANCE_ID`, `GREEN_API_TOKEN`, `MY_PERSONAL_WHATSAPP=919148001667`, `TEST_MODE=false`)
  - `.env.example` (added Green API vars)
  - `PROMPT_LOG.md`
- **Actions Executed**: Live test → `idMessage=3EB0DBF1A8BC033F9A25CC` delivered to `919148001667@c.us`. Fixed phone number format (needs 91 country code prefix). `pytest` → 30 passed. Committed and pushed.

---

### [Prompt #17] - Remove WhatsApp Phone Simulator
- **Timestamp**: 2026-08-30 / Dashboard cleanup
- **Exact User Prompt**: "Please update frontend/index.html to completely remove the Built-in Web WhatsApp Phone Simulator modal/drawer component and its related JS code. Keep the clean dashboard layout focused on: RazorpayX Header, Metric Cards, Search & Filters, Regional Table, and Audit Drawer."
- **Files Created / Modified**:
  - `frontend/index.html` (removed CSS, HTML modal, and all JS for phone simulator; reverted `openAudit()` and `closeDrawer()` to clean state)
  - `PROMPT_LOG.md`
- **Actions Executed**: Stripped all phone simulator code. `pytest` → 30 passed. Committed and pushed.

---

### [Prompt #16] - Interactive 3D WhatsApp Phone Simulator
- **Timestamp**: 2026-08-30 / Frontend phone simulator
- **Exact User Prompt**: "Please add an interactive Web WhatsApp Phone Simulator Drawer/Modal to frontend/index.html: 3D Smartphone Mockup Frame with notch, status bar, and WhatsApp chat header. Dynamic Chat Bubble when user clicks 'Inspect Audit'. Typing Indicator Animation. Interactive Phone Reply Box — type 'STOP' to trigger POST /api/v1/webhooks/whatsapp."
- **Files Created / Modified**:
  - `frontend/index.html` (phone simulator modal CSS, HTML, JS; `openAudit()` now also calls `openPhoneSim()`)
  - `backend/main.py` (new `POST /api/v1/webhooks/whatsapp` endpoint for STOP/OPT OUT opt-out)
  - `PROMPT_LOG.md`, `BUILD_LOG.md`
- **Actions Executed**: Added `#phone-scrim` modal with 3D phone frame, WhatsApp header, typing animation (3 bouncing dots → 1.6s → message bubble), regional recovery message extracted from audit logs, clickable `🔗 Pay via Razorpay UPI` CTA. STOP/OPT OUT in reply box POSTs to `/api/v1/webhooks/whatsapp`, adds phone to opt_out_registry, sets all transactions for that phone to `OPTED_OUT`, and refreshes dashboard. `pytest` → 30 passed.

---

### [Prompt #12] - Twilio WhatsApp Sandbox integration (later removed)
- **Timestamp**: 2026-08-30 / WhatsApp live messaging
- **Exact User Prompt**: "Please update backend/agent.py to install twilio library (pip install twilio) and add a function send_live_whatsapp_message(to_phone, message_text). When a payment failure is processed in backend/main.py, send the generated regional Hinglish/Kanglish recovery message directly to MY_PERSONAL_WHATSAPP using Twilio WhatsApp Sandbox!"
- **Files Created / Modified**:
  - `requirements.txt` (regenerated with `twilio==9.11.0` and dependencies)
  - `.env` + `.env.example` (added Twilio vars — later reverted)
  - `backend/agent.py` (added `send_live_whatsapp_message()` — later removed)
  - `backend/main.py` (wired WhatsApp call in `dispatch_recovery()` — later removed)
  - `PROMPT_LOG.md`, `BUILD_LOG.md`
- **Actions Executed**: Twilio integrated, tested, and confirmed working (messages delivered). Subsequently removed in Prompts #13–#15 at user request after exploring alternatives (Whapi, CallMeBot). Final state: `send_live_whatsapp_message()` does NOT exist in `backend/agent.py`; no Twilio vars in `.env`. The core pipeline (guardrails, LLM agent, audit logs) remains intact.

---

### [Prompt #13–#15] - WhatsApp API exploration and cleanup
- **Timestamp**: 2026-08-30 / Post-Twilio cleanup
- **Summary**: Explored Twilio ContentSid template workaround, CallMeBot, WPSent, WireWeb, and Whapi Cloud as alternative WhatsApp channels. Whapi worked briefly (messages delivered) but hit trial limit. User requested removal of all third-party WhatsApp APIs.
- **Final state after cleanup**:
  - `backend/agent.py` — no messaging functions; LLM diagnostics only
  - `backend/main.py` — no WhatsApp import or send calls; DB committed before returning from `dispatch_recovery()`
  - `.env` / `.env.example` — only 7 original core keys (no Twilio, no Whapi, no CallMeBot vars)
  - `scripts/smoke_api.py` — added `X-API-KEY` header to all protected endpoint calls
- **Tests**: 30 passed
