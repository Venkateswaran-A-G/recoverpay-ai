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

---
*(Future debugging entries will be appended automatically by coding agents during build cycles)*
