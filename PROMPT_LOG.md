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

---
*(Future prompts and file modifications will be appended automatically by Cursor Pro)*
