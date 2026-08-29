# RecoverPay AI — Technical Design Document (System Architecture & Engineering Specification)

**Project Title**: RecoverPay AI  
**Track**: Track 03 — AI Revenue Recovery  
**Target Event**: Razorpay AI Buildathon 2026  
**Role Target**: AI Builder Intern (₹75,000 / month, Bangalore HQ)  
**System Type**: Hybrid Agentic Event-Driven Payment Recovery Engine with Financial Guardrails  

---

## 🏗️ Technical Architecture & System Design Specification

### Q1. What should the complete system architecture look like?

The system follows an **Event-Driven Micro-Monolith Architecture** decoupled into four primary layers:

```
                  +-------------------------------------------------+
                  |               Razorpay Gateway                  |
                  |     (Webhooks / Test Payment Link APIs)          |
                  +------------------------+------------------------+
                                           |
                                  Webhook Event Payload
                                           |
                                           v
+-----------------------------------------------------------------------------------+
|                               RECOVERPAY AI BACKEND                               |
|                                                                                   |
|   +-----------------------+     +-------------------+     +-------------------+   |
|   |  Webhook Ingestion    | --> | Diagnostic Engine | --> | Guardrails Engine |   |
|   |  & HMAC Verification  |     | (LLM + Failure    |     | (Bounded Rules    |   |
|   |  (FastAPI)            |     |  Categorizer)     |     |  State Machine)   |   |
|   +-----------------------+     +-------------------+     +---------+---------+   |
|                                                                     |             |
|                                                                Passed / Flagged   |
|                                                                     |             |
|                                                                     v             |
|   +-----------------------+     +-------------------+     +---------+---------+   |
|   |  Audit Trail Logger   | <-- | Razorpay Link     | <-- | Recovery Dispatch |   |
|   |  (SQLite / PostgreSQL)|     | Generator Service |     | (WhatsApp / SMS)  |   |
|   +-----------------------+     +-------------------+     +-------------------+   |
+------------------------------------------+----------------------------------------+
                                           |
                                  REST API / WebSockets
                                           |
                                           v
+-----------------------------------------------------------------------------------+
|                               NEXT.JS FRONTEND UI                                 |
|                                                                                   |
|  +--------------------+   +-----------------------+   +------------------------+  |
|  | Metrics Overview   |   | Live Execution Graph  |   | Batch Test Simulator   |  |
|  | Cards & Analytics  |   | (Mermaid/Node Tracing)|   | (100 Failure Scenarios)|  |
|  +--------------------+   +-----------------------+   +------------------------+  |
+-----------------------------------------------------------------------------------+
```

1. **Ingestion & Validation Layer**: Ingests Razorpay webhook payloads (`payment.failed`, `subscription.halted`), verifies HMAC SHA256 signatures, and normalizes failure event schemas.
2. **Diagnostic & Intelligence Layer**: An LLM agent (GPT-4o-mini via Vercel AI SDK / LangChain) parses the failure code (`BAD_REQUEST_PAYMENT_TIMED_OUT`, `INSUFFICIENT_FUNDS`) and constructs a failure context + localized Hinglish copy.
3. **Financial Guardrails Engine**: A deterministic, non-LLM Python state machine that evaluates safety rules (Max retries, amount threshold caps, opt-out status).
4. **Action & Outreach Dispatcher**: Calls Razorpay API to generate single-click payment links (`/v1/payment_links`) and dispatches the recovery link via WhatsApp sandbox.
5. **Audit & Analytics Store**: Writes immutable step-by-step logs into SQLite/PostgreSQL and serves REST API endpoints to the Next.js UI dashboard.

---

### Q2. What are the frontend, backend, database, AI, and external-service components?

| Component Layer | Technology Selected | Responsibility |
| :--- | :--- | :--- |
| **Frontend Framework** | **Next.js 14 (App Router)** | Renders real-time dashboard UI, metric cards, visual execution graphs, and batch simulation control panel. |
| **Styling & Icons** | **Tailwind CSS + Lucide Icons + Shadcn UI** | Clean, modern, responsive fintech styling matching Razorpay's design language. |
| **Backend API** | **Python (FastAPI)** | Handles webhooks, runs guardrail evaluation state machine, interacts with Razorpay SDK, and serves dashboard API. |
| **Database** | **SQLite (via SQLAlchemy) / PostgreSQL** | Stores transaction records, audit logs, merchant configuration, and opt-out registries. |
| **AI / LLM Orchestration** | **OpenAI GPT-4o-mini + Pydantic** | Evaluates failure reasons, performs sentiment analysis on customer responses, and generates localized Hinglish outreach scripts with strict JSON schema validation. |
| **External Service 1** | **Razorpay Test API (`razorpay-python`)** | Generates dynamic payment links (`/v1/payment_links`) and receives webhook events (`payment.failed`). |
| **External Service 2** | **Twilio / Meta WhatsApp Sandbox API** | Simulates localized SMS / WhatsApp messaging with payment recovery links. |

---

### Q3. How does data flow through the entire system?

```
[ Customer Payment Fails ]
          │
          ▼ (1) HTTP POST Webhook
[ FastAPI Ingestion Endpoint ]
          │
          ▼ (2) Verify Webhook HMAC Signature & Save Payload
[ Audit Storage: Status = RECEIVED ]
          │
          ▼ (3) Process Payload with Failure Categorizer
[ LLM Diagnostic Module ] ──► Extracts Failure Reason & Crafts Localized Script
          │
          ▼ (4) Evaluate Financial Guardrails Engine
[ Bounded Rules State Machine ]
          │
          ├───► [ Failed Guardrail: e.g. Amount > ₹5,000 ]
          │            │
          │            ▼
          │      Set Status = REQUIRES_HUMAN_APPROVAL ➔ Alert Dashboard
          │
          └───► [ Passed Guardrail: Amount <= ₹5,000 & Retries < 2 ]
                       │
                       ▼ (5) Call Razorpay API
                 [ Razorpay Link Generator Service ]
                       │
                       ▼ (6) Dispatch WhatsApp Outreach
                 [ WhatsApp Messaging Sandbox ]
                       │
                       ▼ (7) Log Execution Trace & Update Dashboard Metrics
                 [ Audit DB: Status = RECOVERY_DISPATCHED ]
```

---

### Q4. What APIs do we need?

#### Internal Backend REST APIs (FastAPI)
1. `POST /api/v1/webhooks/razorpay` — Webhook ingestion endpoint for Razorpay failure events.
2. `GET /api/v1/dashboard/metrics` — Returns aggregated analytics (*Total Failed Volume*, *Recovered Revenue*, *Recovery Rate %*, *Outreach Cost*).
3. `GET /api/v1/audit-logs` — Paginated list of transaction logs with detailed execution traces.
4. `GET /api/v1/audit-logs/{id}` — Single transaction detail endpoint including execution graph nodes and LLM prompts.
5. `POST /api/v1/simulator/run-batch` — Triggers a batch simulation run across 10–100 mock payment failure scenarios.
6. `POST /api/v1/guardrails/approve/{id}` — Endpoint for merchant to manually approve high-value flagged recoveries.

#### External APIs Consumed
1. **Razorpay API**:
   * `POST /v1/payment_links` — Creates dynamic short payment links with custom expiry and amount.
   * `GET /v1/payments/{id}` — Fetches payment status.
2. **OpenAI API**:
   * `POST /v1/chat/completions` (GPT-4o-mini) — Generates structured JSON diagnostics and Hinglish copy.
3. **Twilio / WhatsApp Sandbox API**:
   * `POST /v1/Messages` — Sends WhatsApp message containing the Razorpay Payment Link.

---

### Q5. What database/storage architecture do we need?

We use a relational schema (**SQLite** for local development/hackathon demo, migration-ready for **PostgreSQL**).

#### Primary Database Tables Schema

```sql
-- 1. Transactions Table
CREATE TABLE transactions (
    id VARCHAR(36) PRIMARY KEY,
    razorpay_payment_id VARCHAR(100),
    merchant_id VARCHAR(50) NOT NULL,
    customer_name VARCHAR(100),
    customer_phone VARCHAR(20) NOT NULL,
    customer_email VARCHAR(100),
    amount DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(10) DEFAULT 'INR',
    failure_code VARCHAR(100) NOT NULL,
    failure_reason TEXT,
    recovery_status VARCHAR(50) NOT NULL, -- PENDING, RECOVERY_DISPATCHED, RECOVERED, FLAGGED_FOR_APPROVAL, FAILED_GUARDRAIL, OPTED_OUT
    retry_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Audit Trail Logs Table (Immutable Execution History)
CREATE TABLE audit_logs (
    id VARCHAR(36) PRIMARY KEY,
    transaction_id VARCHAR(36) REFERENCES transactions(id),
    step_name VARCHAR(100) NOT NULL, -- INGESTION, LLM_DIAGNOSIS, GUARDRAIL_CHECK, PAYMENT_LINK_GEN, DISPATCH
    step_status VARCHAR(20) NOT NULL, -- SUCCESS, FAILED, WARNING, BYPASSED
    llm_prompt TEXT,
    llm_response TEXT,
    guardrail_evaluation JSON,
    raw_payload JSON,
    execution_time_ms INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Opt-Out Registry Table (Compliance & Stopping Rules)
CREATE TABLE opt_out_registry (
    phone_number VARCHAR(20) PRIMARY KEY,
    opt_out_source VARCHAR(50), -- WHATSAPP_REPLY, MANUAL_MERCHANT, SMS_STOP
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

### Q6. How will authentication and authorization work?

* **Webhook Authentication**:
  * Every incoming Razorpay webhook request is verified using HMAC SHA256 signature verification:
    `expected_signature = HMAC_SHA256(webhook_secret, raw_request_body)`
  * Requests with invalid or missing signatures are rejected immediately with HTTP `401 Unauthorized`.
* **Dashboard Authorization**:
  * For the hackathon MVP, the dashboard uses a single-tenant API Key / Bearer Token (`X-API-KEY`) configured via environment variables.
  * In a production multi-tenant setup, Clerk or Supabase Auth would issue JWT tokens for merchant user sessions.

---

### Q7. How will we handle sensitive user/payment/business data?

* **Zero Cardholder Data Storage**: RecoverPay AI **never sees or stores raw credit card numbers, CVVs, or bank passwords**. All payment processing happens entirely inside Razorpay's PCI-DSS compliant checkout frames.
* **PII Masking**: Customer phone numbers and email addresses are masked in logging output (`+91 98*****1234`) when displayed in frontend UI traces.
* **Environment Variable Isolation**: API keys (`RAZORPAY_KEY_SECRET`, `OPENAI_API_KEY`, `WEBHOOK_SECRET`) are stored strictly in server-side `.env` files and never exposed to the client-side bundle.

---

### Q8. How will the system behave when an external API or service fails?

| Failure Scenario | Mitigation & Fallback Strategy |
| :--- | :--- |
| **OpenAI API Downtime / Timeout** | System catches the API exception and falls back to a **deterministic pre-written Hinglish recovery template**. Logs `LLM_FALLBACK_TRIGGERED` in audit trail. |
| **Razorpay API Network Error** | Implements exponential backoff retry logic (3 attempts with 2s, 4s, 8s delays) using Python's `tenacity` library. If all retries fail, transaction status transitions to `PENDING_RETRY`. |
| **WhatsApp / Twilio Messaging Failure** | If WhatsApp API fails or number is invalid, system automatically falls back to sending an SMS recovery link or logging a web notification for the merchant. |
| **Invalid LLM JSON Output (Hallucination)** | System validates LLM output using strict **Pydantic schema parsing**. If validation fails, schema parser rejects the completion and triggers the fallback template. |

---

### Q9. How would this architecture scale if usage increased 100×?

If transaction volume scales from 1,000 to 100,000 failed payments per day:

1. **Async Queue Worker Pattern**: Move webhook handling to an asynchronous task queue (**Celery / Redis / AWS SQS**). The FastAPI endpoint acknowledges the webhook in <50ms (`200 OK`) and pushes the payload to Redis for background processing.
2. **Database Scaling**: Migrate from SQLite to **PostgreSQL with Read-Replicas**. Partition `audit_logs` by month to maintain fast query performance.
3. **LLM Caching & Batching**: Implement a Redis vector/exact cache for failure categorization (`BAD_REQUEST_PAYMENT_TIMED_OUT` → pre-cached diagnostic structure) reducing LLM API latency and cost by 80%.
4. **Stateless Scale-Out**: FastAPI backend services are stateless and can be scaled horizontally across multiple Docker containers behind a Cloudflare / AWS Application Load Balancer.

---

### Q10. What technical decisions could become bottlenecks later, and how do we mitigate them?

| Potential Bottleneck | Why It Could Break | Mitigation Plan |
| :--- | :--- | :--- |
| **Synchronous LLM API Calls in Webhook Loop** | OpenAI API latency (1–2 seconds) could block webhook handlers and cause HTTP timeouts from Razorpay servers. | **Mitigation**: Process webhooks asynchronously using Python `asyncio` or background task queues (`BackgroundTasks` in FastAPI). Return `202 Accepted` immediately. |
| **SQLite Concurrent Write Lock (`database is locked`)** | SQLite locks the entire database file during writes under heavy multi-threaded usage. | **Mitigation**: Use SQLAlchemy connection pooling for hackathon demo; migrate to PostgreSQL for multi-user production deployment. |
| **WhatsApp Rate Limits** | Meta WhatsApp Business API enforces tier limits on outgoing marketing/recovery messages per second. | **Mitigation**: Enforce rate-limiting queues (e.g. 10 messages/sec) and batch outreach dispatches. |
| **Large Audit Log Table Size** | Saving full LLM prompts and responses for millions of transactions will bloat database storage rapidly. | **Mitigation**: Set a data retention policy (e.g. archive raw prompts after 30 days; retain only structured execution metadata). |

---

*Technical Design Specification complete and verified for RecoverPay AI — Razorpay AI Buildathon 2026.*
