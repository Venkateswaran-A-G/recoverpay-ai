# AGENTS.md - System Rules & Conventions for RecoverPay AI

## Tech Stack & Architecture
- **Frontend**: Next.js 14 (App Router), Tailwind CSS, Shadcn UI, Lucide Icons, Recharts, Mermaid.js
- **Backend**: Python 3.11, FastAPI, Pydantic v2, SQLAlchemy ORM
- **Database**: SQLite (`recoverpay.db`) for dev/demo; PostgreSQL ready
- **AI & SDKs**: OpenAI GPT-4o-mini (structured JSON), Razorpay Python SDK (`razorpay`)

## 🚨 MANDATORY GIT COMMIT & PUSH RULE
**AFTER EVERY COMPLETED FEATURE, FIX, OR SMALL FILE EDIT, YOU MUST:**
1. Check changed files using `git status` or `git diff`.
2. Stage and commit changes with a **meaningful Conventional Commit message**:
   - `feat: <description>` for new features
   - `fix: <description>` for bug fixes or schema updates
   - `test: <description>` for unit / integration tests
   - `docs: <description>` for documentation updates
   - `refactor: <description>` for code restructuring
3. Automatically execute `git push origin <branch-name>` so every single edit is safely backed up to GitHub.

## Hard System Guardrails (NON-NEGOTIABLE)
1. **Financial Threshold**: ANY transaction amount `> ₹5,000` MUST return `requires_human_approval: true` and set status to `FLAGGED_FOR_APPROVAL`. Never auto-dispatch high-value payments.
2. **Retry Cap**: Maximum 2 recovery outreach retries per customer order. If `retry_count >= 2`, hard-stop and update status to `MAX_RETRIES_REACHED`.
3. **Opt-Out Compliance**: Check `opt_out_registry` table before any outreach. If customer phone exists in table, instantly set status to `OPTED_OUT` and stop.
4. **HMAC Webhook Auth**: Verify `X-Razorpay-Signature` using HMAC SHA256 before parsing incoming webhook JSON body. Return HTTP 401 if invalid.
5. **PII Masking**: Mask phone numbers (`+91 98*****1234`) and email addresses in all frontend UI logs.
6. **No Fake Mocks in Prod Code**: Use explicit `TEST_MODE=true` flags for simulation runs.

## Coding Agent Workflow Rules
- Reference `@AGENTS.md` and `@technical_design_doc.md` before making structural edits.
- Run `pytest` after backend changes and `npm run build` after frontend changes.
- Append all package failures, runtime errors, and fixes into `BUILD_LOG.md`.
- Keep Pydantic models in `backend/schemas.py` and DB ORM models in `backend/models.py`.
- **Commit & Push to GitHub after EVERY feature edit!**
