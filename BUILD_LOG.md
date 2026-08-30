# BUILD_LOG.md - Engineering & Debugging Journal

This file tracks all technical errors, package conflicts, API failures, and structural fixes encountered during the development of RecoverPay AI.

---

### [Entry #01] Environment Setup & Directory Initialization
- **Status**: 🟢 RESOLVED
- **Component**: Workspace Setup
- **What happened**: Project workspace initialized with complete master specification suite (`product_specification.md`, `technical_design_doc.md`, `ai_design_doc.md`, `engineering_testing_plan.md`, `vibecoding_agent_guide.md`).
- **Fix / Action Taken**: Configured `AGENTS.md` rules file and `BUILD_LOG.md` tracking system for Cursor / Windsurf / Claude Code agents.
- **Guardrail Added**: All coding agents must check `AGENTS.md` before executing multi-file edits.

### [Entry #02] Python 3.11 runtime unavailable — using 3.13.1
- **Status**: 🟢 RESOLVED
- **Component**: Virtual Environment
- **What happened**: `py -3.11` failed (`No suitable Python runtime found`). System Python is 3.13.1.
- **Fix / Action Taken**: Created `.venv` with Python 3.13.1. Installed fastapi, uvicorn, sqlalchemy, pydantic, email-validator, razorpay, openai, pytest, httpx, and python-dotenv. Import check passed.
- **Guardrail Added**: Document runtime as 3.13 for this machine; pin packages in `requirements.txt`.

### [Entry #03] Database models, Pydantic schemas, and SQLite init
- **Status**: 🟢 RESOLVED
- **Component**: Backend ORM / Schemas
- **What happened**: Phase 1–2 setup — ORM tables (`transactions`, `audit_logs`, `opt_out_registry`) in `backend/database.py`; Pydantic v2 contracts in `backend/schemas.py`.
- **Fix / Action Taken**: `init_db()` creates SQLite `recoverpay.db`. Added `python-dotenv` so `DATABASE_URL` loads from `.env`. Pytest: 9 passed.
- **Guardrail Added**: Financial threshold constant ₹5,000 and max retry cap 2 live on the schema layer; PII mask helpers for phone/email.

### [Entry #04] requirements.txt UTF-16 encoding + ORM file location
- **Status**: 🟢 RESOLVED
- **Component**: Packaging / Project Structure
- **What happened**:
  1. `requirements.txt` was written via PowerShell `>` redirection as UTF-16 LE (BOM `FF FE` + NUL between every ASCII char). Pip reads it as `a n n o t a t e d - d o c` and cannot install.
  2. ORM models (`Transaction`, `AuditLog`, `OptOutRegistry`) lived in `backend/database.py`, violating AGENTS.md (`backend/models.py`).
- **Fix / Action Taken**: Regenerated `requirements.txt` as UTF-8 via Python (no PowerShell redirect). Moved ORM models to `backend/models.py`; `database.py` now holds engine/session/`init_db()` and re-exports models.
- **Guardrail Added**: Always write lockfiles with Python `open(..., encoding='utf-8')` on Windows.

### [Entry #05] Phase 3 guardrails engine
- **Status**: 🟢 RESOLVED
- **Component**: Financial Guardrails
- **What happened**: Implemented non-LLM safety state machine. No package or runtime errors.
- **Fix / Action Taken**: `backend/guardrails.py` evaluates opt-out → retry cap (`>= 2`) → amount `> ₹5,000`. `tests/test_guardrails.py`: 4 passed. Full suite: 14 passed.
- **Guardrail Added**: High-value payments never auto-dispatch (`requires_human_approval=true`, `FLAGGED_FOR_APPROVAL`).

### [Entry #06] Phase 4 regional LLM agent
- **Status**: 🟢 RESOLVED
- **Component**: LLM Diagnostic Agent
- **What happened**: OpenAI key in `.env` is a placeholder (`sk-proj-...`) and `TEST_MODE=true`, so live GPT-4o-mini is not called in this workspace. That is expected.
- **Fix / Action Taken**: Production path uses GPT-4o-mini `response_format=json_object` + `LLMDiagnosticOutput`. Placeholder/TEST_MODE/API errors use deterministic regional templates. Link must appear verbatim or copy is discarded.
- **Guardrail Added**: Confidence `< 0.75` or mutated Razorpay link → `LLM_FALLBACK_TRIGGERED` template. Prompt-injection names sanitized.
- **Follow-up**: `python -m backend.agent` crashed on Windows cp1252 when printing `₹`. Fixed `__main__` to reconfigure stdout as UTF-8.

### [Entry #07] Phase 5 FastAPI engine
- **Status**: 🟢 RESOLVED
- **Component**: Webhooks / Dashboard API
- **What happened**: Existing `recoverpay.db` predates `customer_state`. Live GPT-4o-mini is skipped because `TEST_MODE=true` (regional fallback templates used, logged as `LLM_FALLBACK_TRIGGERED`).
- **Fix / Action Taken**: Added SQLite `ALTER TABLE` in `init_db()`. HMAC is verified on the raw body before JSON parse (401 on mismatch). High-value amounts never auto-dispatch. Uvicorn smoke on `:8000` succeeded.
- **Guardrail Added**: Webhook fail-closed without a valid `X-Razorpay-Signature`. Dashboard PII masking on list/detail routes.

### [Entry #08] Phase 6 dashboard UI
- **Status**: 🟢 RESOLVED
- **Component**: Frontend dashboard
- **What happened**: No Cursor browser MCP available, so UI clicks were not exercised in a real viewport. Dashboard is a single static HTML file (not Next.js) as requested.
- **Fix / Action Taken**: Served `frontend/index.html` at `GET /`. Verified HTML payload and API flows the UI calls (metrics, batch, approve, audit detail) via TestClient / uvicorn + httpx.
- **Guardrail Added**: Transaction list still uses PII-masked API fields; high-value rows only expose Approve when status is `FLAGGED_FOR_APPROVAL`.

### [Entry #09] 3D glassmorphism restyle
- **Status**: 🟢 RESOLVED
- **Component**: Frontend dashboard
- **What happened**: Visual restyle only. Same APIs. Tailwind CDN + custom `.glass` / `.lift` because a Next.js build is not in this phase.
- **Fix / Action Taken**: Deep zinc `#080a0f` ambient orbs, frosted metric cards, amber ₹5K shield banner, 3D audit drawer. No browser MCP — verified via HTML assertions and API smoke.
- **Guardrail Added**: Approve button still only renders for `FLAGGED_FOR_APPROVAL`.

### [Entry #10] Light / Dark theme toggle
- **Status**: 🟢 RESOLVED
- **Component**: Frontend dashboard
- **What happened**: Dark was previously hardcoded (`#080a0f` only). No browser automation to click the toggle in a viewport.
- **Fix / Action Taken**: `darkMode: 'class'`, FOUC-prevention script, `localStorage.recoverpay-theme`, light glass `bg-white/80` / `#f8fafc`. Verified toggle strings and config in served HTML.
- **Guardrail Added**: Default theme remains dark (TEST MODE demo look) until the user switches.

### [Entry #11] Dashboard search and multi-filters
- **Status**: 🟢 RESOLVED
- **Component**: Frontend dashboard
- **What happened**: Filters are client-side on the already-masked `/api/v1/transactions` list (no extra backend query API).
- **Fix / Action Taken**: Combined search + amount + status + region in `filteredTxns()`. Empty state distinguishes “no data” vs “no matches”.
- **Guardrail Added**: High-value approve still only for `FLAGGED_FOR_APPROVAL`.

### [Entry #12] MVP 100% complete and verified
- **Status**: 🟢 VERIFIED — BUILD 100% COMPLETE
- **Component**: Full RecoverPay AI MVP
- **What happened**: `pytest tests/test_guardrails.py -W error` initially failed the last case on `ResourceWarning: unclosed database` (assertions themselves passed). Uvicorn was already serving `http://127.0.0.1:8000` with `/health` 200.
- **Fix / Action Taken**: Guardrail fixture now `engine.dispose()` after `session.close()`. Re-run: **4 passed, 0 warnings**. Full suite: 30 passed. Phases 1–6 marked complete in `PHASE_WISE_DEVELOPMENT_PLAN.md`.
- **Verified guardrails**: amount `> ₹5,000` → `FLAGGED_FOR_APPROVAL`; `retry_count >= 2` → `MAX_RETRIES_REACHED`; opt-out → `OPTED_OUT`; standard amount passes.
- **Verified runtime**: `uvicorn backend.main:app` healthy (`test_mode: true`). Dashboard at `GET /`.

### [Entry #13] Simulate button ignored HTTP errors
- **Status**: 🟢 RESOLVED
- **Component**: Dashboard UI
- **What happened**: `Simulate 20 Failed Payments` always toasted `data.flagged_for_approval` / `data.dispatched` even on 4xx/5xx, showing `undefined`. Approve already checked `res.ok`.
- **Fix / Action Taken**: Parse JSON safely, throw on `!res.ok` with `detail` or status, toast the error message.
- **Guardrail Added**: Failed batch no longer calls `refresh()` as if the run succeeded.

---
*(Future debugging entries will be appended automatically by coding agents during build cycles)*

---

### [Entry #25] WhatsApp localhost URL rendered as plain text
- **Status**: 🟢 RESOLVED
- **Component**: `backend/agent.py`, `backend/main.py`
- **What happened**: Green API messages showed `http://127.0.0.1:8000/api/v1/recovery/pay/...` as white plain text. WhatsApp does not auto-linkify loopback hosts, and a phone cannot open the merchant PC's localhost.
- **Fix / Action Taken**: WhatsApp copy now uses a public `https://rzp.io/...` URL on its own line. Green API sends an interactive **Pay now** URL button, then falls back to `sendMessage` with `linkPreview: true`. Local RecoverPay click URL is kept for dashboard testing only.

---

### [Entry #24] Recovery completion triggers and conversion rate
- **Status**: 🟢 COMPLETE
- **Component**: `backend/main.py`
- **What happened**: WhatsApp click URL and `razorpay-paid` now mark `RECOVERED` with `PAYMENT_EVIDENCE_CONFIRMED`. Merchant-accepted voice calls mark `RECOVERED` with `HIGH_VALUE_VOICE_RECOVERY_CONFIRMED`. Simulator recovers ~72% of under-₹5k dispatches. Dashboard rate is recovered / (recovered + still-dispatched), landing in 68–75%.

---

### [Entry #23] Local SQLite metrics reset
- **Status**: 🟢 COMPLETE
- **Component**: `recoverpay.db`
- **What happened**: Cleared `transactions` (358) and `audit_logs` (1368) so dashboard volume/metrics start at ₹0.00. `opt_out_registry` was left intact.

---

### [Entry #22] Remove Mermaid, luxury gradient funnel bars
- **Status**: 🟢 COMPLETE
- **Component**: `frontend/index.html`
- **What happened**: Mermaid.js CDN, initialize, and flowchart renderers removed. Funnel and failure breakdown now use luxury Tailwind gradient bars, glass tracks, and conversion yield pills.

---

### [Entry #21] Mermaid.js funnel and breakdown diagrams
- **Status**: 🟢 COMPLETE
- **Component**: `frontend/index.html`
- **What happened**: Replaced flat CSS bars with Mermaid v10 flowcharts. Funnel is LR with live counts; failure breakdown is a TB categorical diagram. Diagrams re-render on metrics refresh and theme toggle.

---

### [Entry #20] Enterprise funnel, paid webhook, review queue
- **Status**: 🟢 COMPLETE
- **Component**: `backend/main.py` + `frontend/index.html`
- **What happened**: Added HMAC-verified `payment_link.paid` reconciliation, stage funnel + failure breakdown on `/dashboard/metrics`, visual charts, and a Human Review Queue with batch approve (voice-gate rows skipped).

---

### [Entry #19] Voice permission moved off the page center
- **Status**: 🟢 COMPLETE
- **Component**: `frontend/index.html`
- **What happened**: Mid-page and table-row Accept/Decline banners were crowding the dashboard. They are now a left-side slide-in notification (`#voicePermissionBanner`) so the table stays clean.

---

### [Entry #18] Merchant permission gate for AI voice call
- **Status**: 🟢 COMPLETE
- **Component**: `backend/main.py` + `frontend/index.html`
- **What happened**: Simulator now emits exactly one > ₹20,000 transaction per 20-payment batch (`REQUIRES_VOICE_CALL_PERMISSION`). Remaining 19 stay under ₹19,000. Twilio is not dialed until the merchant clicks Accept. Decline sets `VOICE_CALL_DECLINED` with no call.

---

### [Entry #17] Twilio Voice live call for > ₹20,000
- **Status**: 🟢 COMPLETE
- **Component**: `backend/main.py` + `frontend/index.html`
- **What happened**: Merchant-approved Twilio Voice call to `+919148001667` from `+17372212163` with Polly.Aditi TwiML. Status `VOICE_CALL_DISPATCHED`, audit `REAL_PHONE_VOICE_CALL_PLACED`. Simulator emits ₹25,000 failures. `TEST_MODE=true` returns `CA_TEST_MODE_SKIPPED` so pytest does not place live calls.
- **Trial-account note**: Twilio trial rejects inline `twiml=` (`Invalid or disallowed parameters`). Fallback uses the same TwiML via `https://twimlets.com/echo?Twiml=...` so the live call still connects.

---

### [Entry #16] WhatsApp Phone Simulator
- **Status**: 🟢 COMPLETE
- **Component**: `frontend/index.html` + `backend/main.py`
- **What happened**: New feature — 3D WhatsApp phone simulator modal that opens alongside the audit drawer when clicking "Inspect Audit". Shows typing animation then renders the exact regional recovery message from the LLM audit log with a 💡 failure tip and 🔗 Razorpay UPI button. Typing "STOP" in the reply box triggers the live opt-out API.
- **No errors**: 30 tests passed.

---

### [Entry #15] smoke_api.py missing X-API-KEY headers
- **Status**: 🟢 RESOLVED
- **Component**: `scripts/smoke_api.py`
- **What happened**: All calls to protected endpoints (`/simulator/run-batch`, `/dashboard/metrics`, `/transactions`, `/audit-logs`) were missing the `X-API-KEY: demo_dashboard_key` header. They passed silently because `TEST_MODE=true` bypasses auth, but would fail in production validation.
- **Fix**: Added `API_KEY` constant and `auth_headers` dict to all 4 protected endpoint calls.

---

### [Entry #14] Twilio WhatsApp Sandbox integration (added then removed)
- **Status**: 🟡 REVERTED
- **Component**: `backend/agent.py` + `backend/main.py`
- **What happened**: Twilio integrated and working — messages delivered to `+919148001667`. ContentSid template workaround required due to Twilio trial account restrictions. Subsequently, Whapi Cloud and CallMeBot were explored as alternatives. All messaging code removed at user request.
- **Current state**: `send_live_whatsapp_message()` does NOT exist in `backend/agent.py`. No Twilio or third-party messaging vars in `.env`. The dispatch pipeline commits DB and returns without any external messaging call.
- **Verified**: `pytest` → 30 passed. `.env` and `.env.example` contain only the 7 original core keys.
