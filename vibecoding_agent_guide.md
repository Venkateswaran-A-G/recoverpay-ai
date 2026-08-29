# RecoverPay AI — Coding Agent Setup & Master Vibecoding Guide

**Project Title**: RecoverPay AI  
**Track**: Track 03 — AI Revenue Recovery  
**Target Event**: Razorpay AI Buildathon 2026  
**Role Target**: AI Builder Intern (₹75,000 / month, Bangalore HQ)  
**Document Purpose**: Definitive Guide for Coding Agents (Cursor, Claude Code, Windsurf, v0)  

---

## 🤖 Coding Agent Strategy, Tooling & Master Prompt Setup

### Q1. Which tool is best: Cursor, Antigravity, Claude Code, etc.?

For building a complete full-stack AI fintech app like **RecoverPay AI**, the single best setup is a **Hybrid Agent Workflow**:

```
+-----------------------------------------------------------------------------------+
|                           RECOMMENDED AGENT TOOLING                               |
|                                                                                   |
|  1. UI GENERATION         2. FULL-STACK CODING          3. TERMINAL & REFACTORING |
|     -----------------        ------------------            ---------------------- |
|     v0.dev (by Vercel)  ➔    Cursor / Windsurf         ➔   Claude Code CLI        |
|     (Prompts modern React    (VS Code fork with Agent      (Terminal agent for    |
|      dashboards & graphs)     Composer & context workspace) test runs & git diffs) |
+-----------------------------------------------------------------------------------+
```

1. **Cursor (Best Overall Primary IDE Agent)**:
   * *Why*: Cursor's **Composer (Agent Mode)** can read your entire workspace (`@workspace`), write multi-file edits simultaneously (e.g., updating frontend types + FastAPI route + DB schema at the same time), and fix terminal errors automatically.
2. **Claude Code CLI (Best Terminal Agent & Test Debugger)**:
   * *Why*: Claude Code runs inside your terminal, executes `pytest` or `npm run build`, reads failure traces directly, and refactors code autonomously.
3. **v0.dev (Best UI Layout Generator)**:
   * *Why*: Converts plain English descriptions into production-ready Next.js 14 + Tailwind + Shadcn React components in under 30 seconds.

---

### Q2. Is premium worth paying for?

**YES, 100% WORTH IT.**

* **Cursor Pro / Windsurf Pro ($20/month)**: Gives access to Claude 3.5 Sonnet and GPT-4o with unlimited agentComposer edits. Claude 3.5 Sonnet is currently the highest-rated model for code generation, architectural reasoning, and multi-file editing.
* **Cost vs. Value Math**: Paying $20 for a single month during the Buildathon saves you 40+ hours of manual coding syntax debugging. If selected for the ₹75,000/month internship, the ROI is over **3,750x**.

---

### Q3. What skills/context should we give the coding agent?

To turn your coding agent into a senior staff engineer, give it access to these 4 context files in your repository:

1. **`AGENTS.md`**: Project rules, tech stack rules, code style, and hard safety guardrails.
2. **`product_specification.md`**: Business logic, MVP feature set, and user flows.
3. **`technical_design_doc.md`**: System architecture, database schemas, and REST API routes.
4. **`ai_design_doc.md`**: Pydantic schemas, LLM prompts, and guardrail rules.

In Cursor/Windsurf, you reference them by typing `@AGENTS.md @technical_design_doc.md`.

---

### Q4. What master instruction should we give it?

Copy-paste this exact **Master Agent System Prompt** into your Cursor/Windsurf `.cursorrules` or system prompt box:

```markdown
### MASTER SYSTEM INSTRUCTION FOR RECOVERPAY AI

You are a Lead AI Systems Engineer building "RecoverPay AI" for the Razorpay AI Buildathon (Track 03: AI Revenue Recovery).

### YOUR CORE DIRECTIVE:
1. Always reference @AGENTS.md before editing code.
2. Never write mock fallback data directly inside production code—use clean `TEST_MODE` flags.
3. Enforce strict Pydantic v2 schemas on all LLM responses.
4. Ensure every financial action (> ₹5,000 threshold or > 2 retries) passes through `guardrails.py`.
5. Maintain immutable audit logging in `database.py` for every action.
6. Write unit tests in `/tests` for every feature you build before marking the task complete.
7. If an error or package conflict occurs, log the issue and fix in `BUILD_LOG.md`.

### TECH STACK BOUNDARIES:
- Frontend: Next.js 14 (App Router), Tailwind CSS, Lucide Icons, Recharts.
- Backend: Python 3.11, FastAPI, Pydantic v2, SQLAlchemy, Razorpay Python SDK.
- LLM: OpenAI GPT-4o-mini with structured JSON parsing.
```

---

### Q5. How should we divide development into tasks? (Sprint Breakdown)

To avoid breaking your project, build in 5 incremental, testable phases:

```
[ Phase 1: Core Setup ] ➔ [ Phase 2: Backend & Guardrails ] ➔ [ Phase 3: Razorpay & LLM ]
                                                                      │
                                                                      ▼
[ Phase 5: Demo & Evals ] ◄── [ Phase 4: Next.js UI Dashboard ] ◄──────┘
```

* **Phase 1: Core Setup & Schema (Day 1)**:
  * Initialize Next.js frontend and FastAPI backend.
  * Setup SQLite database with SQLAlchemy models (`transactions`, `audit_logs`, `opt_out_registry`).
  * Create `AGENTS.md` and `BUILD_LOG.md`.
* **Phase 2: Backend Ingestion & Guardrails Engine (Day 2)**:
  * Build FastAPI webhook endpoint with HMAC SHA256 signature verification.
  * Implement `guardrails.py` state machine (Amount cap > ₹5,000, max 2 retries, opt-out check).
  * Write unit tests in `tests/test_guardrails.py`.
* **Phase 3: LLM Diagnostic & Razorpay Payment Links (Day 3)**:
  * Build `agent.py` using GPT-4o-mini with Pydantic output validation.
  * Integrate Razorpay Python SDK for `/v1/payment_links` generation.
  * Add automatic fallback template trigger if LLM fails.
* **Phase 4: Next.js Dashboard & Audit Trail UI (Day 4)**:
  * Build Metrics Overview Cards (Failed Volume, Recovered Amount, Rate %, Cost).
  * Build Interactive Audit Trail table and visual Execution Node Graph.
  * Build Batch Simulation Control Panel (run 10-100 test scenarios).
* **Phase 5: Evals Suite & Pitch Recording (Day 5)**:
  * Run `/tests` suite and verify 100% pass rate.
  * Record 5-minute pitch video following the winning narrative framework.

---

### Q6. How should Git/version control work?

Follow a clean, feature-branch Git workflow so you can revert if an agent introduces bad code:

1. **Main Branch (`main`)**: Clean, working production code only.
2. **Feature Branches**:
   * `git checkout -b feature/guardrails-engine`
   * `git checkout -b feature/razorpay-payment-links`
   * `git checkout -b feature/nextjs-dashboard`
3. **Commit Convention**:
   * `feat: add HMAC SHA256 webhook signature validation`
   * `fix: handle Pydantic JSON parsing error on GPT-4o-mini response`
   * `test: add unit test for > ₹5,000 amount cap guardrail`
4. **Before Merging**:
   * Run `pytest` and `npm run build`. If both pass, merge to `main`.

---

### Q7. How should the agent test each feature before moving on?

Force the agent to follow a strict **3-step validation cycle** for every task:

```
[ Step 1: Write Code & Feature ] ➔ [ Step 2: Run Automated Test ] ➔ [ Step 3: Verify & Log ]
                                                  │
                                          Does test pass?
                                         /               \
                                     YES                NO
                                     /                     \
                      [ Merge Feature Branch ]    [ Log Bug in BUILD_LOG.md & Auto-Fix ]
```

1. **Step 1: Write Test First (TDD)**:
   * When asked to build a feature (e.g. amount cap guardrail), tell Cursor: *"First, create `tests/test_guardrails.py` asserting that amount = 6000 returns `requires_approval = True`. Run pytest to confirm it fails."*
2. **Step 2: Implement Feature**:
   * Agent writes implementation in `guardrails.py`.
3. **Step 3: Execute Test & Log Result**:
   * Agent executes `pytest tests/test_guardrails.py` in terminal.
   * If it passes 🟢: Task is marked complete.
   * If it fails 🔴: Agent reads terminal traceback, logs bug in `BUILD_LOG.md`, fixes code, and re-runs test.

---

*Master Vibecoding & Agent Guide complete for RecoverPay AI — Razorpay AI Buildathon 2026.*
