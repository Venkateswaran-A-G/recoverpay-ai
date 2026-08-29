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

---
*(Future debugging entries will be appended automatically by coding agents during build cycles)*
