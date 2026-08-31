# RecoverPay AI — A-to-Z Interview Master Guide

**How to use this file:** Read it once end-to-end. Before a panel, skim the **30-second pitch**, **numbers**, **state machine**, and **rapid-fire Q&A**. Speak in simple sentences first, then drop the engineering term.

This document describes **what we actually shipped**, not only the original spec. Where the spec said Next.js, the live product is FastAPI serving `frontend/index.html`.

---

## 1. The 30-second pitch (memorize this)

In India, **15–20% of checkouts fail** at the last step — bank timeout, low balance, OTP drop. Merchants send a generic email the next day. Almost nobody comes back. That is **revenue leakage**.

**RecoverPay AI** is an **event-driven recovery engine**. When Razorpay fires `payment.failed`, we:

1. Verify the webhook with **HMAC SHA256**.
2. Let an **LLM diagnose** the failure and write a **regional WhatsApp** message.
3. Run a **deterministic guardrail state machine** (not the LLM) so we never spam, never auto-pay high value, never message opted-out users.
4. Send a **1-click pay link**. When the customer taps it, status moves **RECOVERY_DISPATCHED → RECOVERED**.

We prove it with a **batch simulator**, a **live audit trail**, and **metrics** (failed volume, recovered revenue, conversion rate, outreach ROI).

**One line:** *Hybrid agent — probabilistic AI for language, deterministic Python for money and compliance.*

---

## 2. Why this project (Track 03)

| Topic | What you say |
|---|---|
| Event | Razorpay AI Buildathon 2026, **Track 03: AI Revenue Recovery** |
| Bar | Not a chatbot. Show **measured money recovered**, **stopping rules**, **audit trail** |
| Users | Merchant ops (dashboard) + customer (WhatsApp / voice) |
| Demo merchant | **KetoKrafts D2C** (fictional D2C brand) |

If they ask “why not fraud detection?”: Track 02 is risk. We recover **failed legitimate payments**, we do not score fraud.

---

## 3. The problem in engineering terms

**Checkout drop-off / payment degradation.** Gateway returns `payment.failed` with codes like `BAD_REQUEST_PAYMENT_TIMED_OUT`, `INSUFFICIENT_FUNDS`, `AUTHENTICATION_FAILED`.

Current industry path:

`fail → static email 24h later → 0–5% conversion`

We want:

`fail → diagnose in <1s → WhatsApp with 1-click UPI link → measured recovery`

**Why WhatsApp:** India email open rates are poor; WhatsApp open rates are high. **Why now:** cheap fast LLMs + Razorpay payment links + webhooks.

**Impact story:** ₹1 Cr/month GMV × 15–20% fail ≈ **₹15–30 L leaked / month**. Recovering even a fraction pays for outreach (we model outreach at a small ₹ cost per dispatch).

---

## 4. What we actually built (stack)

| Layer | Reality in this repo |
|---|---|
| Backend | **Python + FastAPI** (`backend/main.py`) |
| Validation | **Pydantic v2** (`backend/schemas.py`) |
| ORM | **SQLAlchemy** (`backend/models.py`) |
| DB | **SQLite** `recoverpay.db` (PostgreSQL-ready via `DATABASE_URL`) |
| Dashboard | **Single-page UI** `frontend/index.html` (Tailwind), served by FastAPI at `/` |
| AI | **OpenAI GPT-4o-mini**, JSON mode, fallback templates |
| Payments | **Razorpay** payment links + HMAC webhooks |
| WhatsApp | **Green API** (not Twilio WhatsApp; Twilio WhatsApp was removed) |
| Voice | **Twilio Voice** only for **> ₹20,000**, merchant must Accept first |
| Tests | **pytest** (~46 tests) |
| Launch | `run.bat` / `run.sh` → uvicorn `:8000` + browser |

**Honest correction if they read AGENTS.md:** the original design said Next.js 14. We shipped faster with FastAPI + one HTML dashboard. That is a valid MVP trade-off: one process, one port, no Node build.

---

## 5. Architecture (draw this on a whiteboard)

```
Customer checkout fails
        │
        ▼
Razorpay  ──HMAC──►  POST /api/v1/webhooks/razorpay
        │
        ▼
  Ingest + save Transaction
        │
        ▼
  Guardrails (Python, ordered)
        │
        ├── OPTED_OUT / MAX_RETRIES → stop
        ├── amount > ₹20,000 → REQUIRES_VOICE_CALL_PERMISSION (no auto-dial)
        ├── amount > ₹5,000  → FLAGGED_FOR_APPROVAL (human Approve)
        └── else → diagnose + payment link + WhatsApp
        │
        ▼
  Status RECOVERY_DISPATCHED
        │
        ├── Customer opens /pay/{id}     → RECOVERED + PAYMENT_EVIDENCE_CONFIRMED
        └── Razorpay payment_link.paid   → same (HMAC)
```

**Name it:** event-driven **micro-monolith** (one FastAPI app, clear modules, not 10 microservices).

**Modules:**

| File | Job |
|---|---|
| `backend/main.py` | HTTP, pipeline, metrics, simulator, voice, pay click |
| `backend/guardrails.py` | Opt-out, retry cap, ₹5k flag |
| `backend/agent.py` | Locale, LLM, dual-script WhatsApp, Green API send |
| `backend/razorpay_client.py` | HMAC verify, payment link create |
| `backend/models.py` | ORM tables |
| `backend/schemas.py` | API + LLM contracts, PII mask helpers |
| `backend/tunnel.py` | Public HTTPS so a phone can hit `/pay/{id}` |

---

## 6. End-to-end happy path (say this slowly)

1. **Ingest:** Razorpay POSTs `payment.failed`. We check `X-Razorpay-Signature` = HMAC-SHA256(secret, raw body). Bad signature → **401**. We never trust JSON until the signature is valid.
2. **Persist:** Insert `transactions` row, write `INGESTION` audit.
3. **Guardrails:** Pure Python. Order is **opt-out → retry cap → amount**. LLM cannot override this.
4. **If auto-allowed (≤ ₹5,000, retries &lt; 2, not opted out):**
   - Generate a RecoverPay pay URL (`/pay/{uuid}`) that is publicly reachable (Cloudflare tunnel in demo).
   - LLM (or regional fallback) writes dual-script copy.
   - Green API sends WhatsApp to the configured number.
   - Status = **RECOVERY_DISPATCHED**, audit **DISPATCH**.
5. **Evidence:** Customer taps the link → GET `/pay/{id}` → **RECOVERED** + **PAYMENT_EVIDENCE_CONFIRMED**. Dashboard polls every 3 seconds so the pill updates.

**High value:** ₹5,001–₹20,000 sits in Human Review. Merchant clicks Approve → then same dispatch. **> ₹20,000** never auto-dials; left banner Accept / Decline. Accept places Twilio call then marks recovered (demo of authorized high-value recovery).

---

## 7. Status state machine (they will ask this)

| Status | Meaning |
|---|---|
| `PENDING` | Ingested, not yet blocked or dispatched |
| `RECOVERY_DISPATCHED` | WhatsApp (or approved path) sent; waiting for pay |
| `RECOVERED` | Click or paid webhook confirmed |
| `FLAGGED_FOR_APPROVAL` | Amount **> ₹5,000** and **≤ ₹20,000**; no auto WhatsApp |
| `REQUIRES_VOICE_CALL_PERMISSION` | Amount **> ₹20,000**; merchant must Accept |
| `VOICE_CALL_DECLINED` | Merchant said no; no Twilio call |
| `OPTED_OUT` | Phone in `opt_out_registry` |
| `MAX_RETRIES_REACHED` | `retry_count >= 2` |
| `BANK_OUTAGE_HOLD` | Downstream bank looks down; hold outreach |
| `RETRY_SCHEDULED_POST_BANK_RECOVERY` | Bank came back; retry queued |
| `PENDING_RETRY` | Scheduled for another outreach (still under retry cap) |
| `VOICE_CALL_DISPATCHED` | Twilio call was placed (then typically RECOVERED in demo) |
| `FAILED_GUARDRAIL` | Generic block |

**Voice vs WhatsApp threshold:** two caps — **₹5,000** (human approval for WhatsApp auto-send) and **₹20,000** (voice permission, no auto-dial).

---

## 8. Guardrails — the interview gold

**Why not let GPT decide “is ₹12,000 safe?”**  
LLMs **hallucinate** and are **non-deterministic**. Money, retries, and DND are **policy**. Policy belongs in **code**.

**Order (must recite):**

1. **Opt-out** → stop. Normalize last 10 digits so `+91…` and `91…` match.
2. **Retry cap 2** → `MAX_RETRIES_REACHED`.
3. **Amount > 5000** → `FLAGGED_FOR_APPROVAL`, `requires_human_approval=true`. Never auto-dispatch.

**Approve All** skips **> ₹20,000** (those need the voice banner).

This is **bounded agency**: the agent can talk; it cannot spend or spam past the gates.

---

## 9. AI layer — what GPT does and does not

**Does:**

- Map messy failure text into categories: `TEMPORARY_OUTAGE`, `INSUFFICIENT_FUNDS`, `EXPIRED_CARD`, `AUTHENTICATION_FAILED`, `USER_DROPOFF`.
- Write **dual-script** WhatsApp: native Indic **plus** Latin (Kanglish, Tanglish, etc.). Default English is single script.
- Must copy the **payment_link character-for-character**.

**Does not:**

- Move money, approve ₹5k+, dial the phone, skip opt-out, invent discounts, invent URLs.

**Safety net:**

- `response_format=json_object` + **Pydantic** `LLMDiagnosticOutput`.
- Confidence &lt; 0.75 → **fallback templates**.
- Link missing/changed → fallback.
- Missing API key or `TEST_MODE=true` → fallback (no live OpenAI).
- If GPT forgets Kannada/Tamil/… Unicode, we **rewrite** with `build_rich_whatsapp_message`.

**Locales:** Karnataka→Kannada+Kanglish, TN→Tamil+Tanglish, TS/AP→Telugu, MH→Marathi+Hinglish, Delhi/North→Hindi+Hinglish.

**Phrase:** *Structured generation with a schema gate, not a free-form chatbot.*

---

## 10. WhatsApp, links, and “click = recovered”

**Channel:** Green API `sendMessage` / interactive URL button. Destination is `MY_PERSONAL_WHATSAPP` in demo.

**Why not put `http://127.0.0.1` in WhatsApp?**  
WhatsApp does not turn localhost into a blue link. On a phone, 127.0.0.1 is **the phone**, not your laptop. So we expose **`https://…trycloudflare.com/pay/{id}`**.

**Why not only `rzp.io`?**  
A Razorpay short link is clickable, but RecoverPay **never sees the tap**, so the dashboard stays `RECOVERY_DISPATCHED`. Our `/pay/{id}` **is** RecoverPay, so GET → `RECOVERED`.

**Paid path:** `POST /api/v1/webhooks/razorpay-paid` still HMAC-checks and marks recovered if they actually pay.

**Live simulator:** does **not** auto-mark 72% recovered (so a real tap can change the pill). **pytest** still auto-recovers ~72% under ₹5k because tests set `TEST_MODE=true`.

---

## 11. Voice (&gt; ₹20,000)

- Ingest → `REQUIRES_VOICE_CALL_PERMISSION`.
- **No auto-dial.** Left-side merchant toast: Accept / Decline.
- Accept → Twilio Voice (`Polly.Aditi` / Twimlets fallback on trial) + WhatsApp dispatch → status **RECOVERED** + audit `HIGH_VALUE_VOICE_RECOVERY_CONFIRMED`.
- Decline → `VOICE_CALL_DECLINED`, no call.

**Why a second threshold?** A ₹25,000 recovery should not be a silent WhatsApp; it is a **human-authorized** high-value action.

---

## 12. Bank health widget

HEAD probes / keyword map for SBI, HDFC, ICICI, Axis, Kotak. If a bank looks down, new matching failures can go **BANK_OUTAGE_HOLD** instead of nagging the customer. Simulator can fake an SBI outage. Demo of **adaptive recovery**, not blind retries.

---

## 13. Database (three tables)

**transactions** — one failed payment: amount, phone, state, `recovery_status`, `retry_count`, Razorpay payment id.

**audit_logs** — append-only steps: `INGESTION`, `GUARDRAIL_CHECK`, `LLM_DIAGNOSIS` / `LLM_FALLBACK_TRIGGERED`, `PAYMENT_LINK_GEN`, `DISPATCH`, `PAYMENT_EVIDENCE_CONFIRMED`, voice steps. Stores prompt/response JSON and `execution_time_ms`.

**opt_out_registry** — phone PK. Presence = never message.

**PII on the UI:** `mask_phone` → `+91 98*****1234`, `mask_email` → `r***@domain.com`. Raw values stay in DB for ops.

---

## 14. Metrics (know the formula)

- **Failed volume** = sum of all transaction amounts.
- **Recovered revenue** = sum where status = `RECOVERED`.
- **Recovery rate %** = `recovered_count / (recovered_count + still RECOVERY_DISPATCHED) × 100`  
  (conversion of **open recoveries**, not diluted by flagged ₹25k rows.)
- **Outreach cost** = (successful DISPATCH audits) × cost per message.
- **Net ROI** = recovered revenue / outreach cost.
- **Funnel:** ingested → AI diagnosed → policy approved → action executed → payment verified.

---

## 15. API cheat sheet

| Method | Path | Point |
|---|---|---|
| POST | `/api/v1/webhooks/razorpay` | Failed payment ingest, HMAC, 202 |
| POST | `/api/v1/webhooks/razorpay-paid` | Paid evidence → RECOVERED |
| GET | `/pay/{id}` | WhatsApp 1-click → RECOVERED |
| GET | `/api/v1/recovery/pay/{id}` | Same, longer path |
| GET | `/api/v1/dashboard/metrics` | Cards + funnel |
| GET | `/api/v1/transactions` | Table (masked PII) |
| GET | `/api/v1/audit-logs` | All audit rows |
| GET | `/api/v1/audit-logs/{id}` | Inspect graph + 3D phone preview |
| POST | `/api/v1/guardrails/approve/{id}` | Human approve ₹5k–20k |
| POST | `/api/v1/guardrails/approve-all` | Bulk, skip &gt;20k |
| POST | `/api/v1/voice/approve-and-call/{id}` | Merchant Accept |
| POST | `/api/v1/voice/decline/{id}` | No dial |
| POST | `/api/v1/simulator/run-batch` | 20-payment demo |
| POST | `/api/v1/simulator/bank-outage` | Fake a bank outage for the widget |
| GET | `/api/v1/bank-health` | Bank widget |
| POST | `/api/v1/webhooks/whatsapp` | Opt-out / STOP |
| GET | `/health` | Liveness + `test_mode` |

Dashboard calls use header **`X-API-KEY: demo_dashboard_key`** when `TEST_MODE=false`.

---

## 16. Security (panel loves this)

| Control | How |
|---|---|
| Webhook authenticity | HMAC SHA256, **raw body**, not re-serialized JSON |
| Secrets | `.env` gitignored; `.env.example` placeholders |
| PII | Mask in UI and some audit payloads |
| Authz | API key on dashboard routes when not test mode |
| TEST_MODE | No live OpenAI / Green API / Twilio in tests |
| Pay click | Idempotent if already `RECOVERED` |

**HMAC gotcha:** You must hash the **exact bytes** Razorpay sent. `json.dumps` can change key order and break the signature.

---

## 17. Simulator (what “Run 20” does)

Mix of states (KA, TN, TS, MH, Delhi), failure codes, names.

Typical 20-row mix:

- Most under ₹5,000 → auto WhatsApp (`RECOVERY_DISPATCHED` in live mode until click).
- Some ₹7,500 → Human Review.
- **Exactly one &gt; ₹20,000** → voice permission banner.
- Some `retry_count=2` → max retries.
- One opt-out phone → `OPTED_OUT`.

---

## 18. How to run

```
run.bat          # Windows: uvicorn 0.0.0.0:8000 --reload, open browser
./run.sh         # Mac/Linux
```

Or: `python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload`

Open **http://localhost:8000**.

---

## 19. Demo script (3–5 min)

1. **Hook:** 15–20% Indian checkouts die at pay. Email is too late.
2. **Show dashboard** empty or live metrics.
3. **Simulate 20.** Point at: flagged ₹7.5k, one ₹25k voice row, dispatched WhatsApp.
4. **Inspect Audit** on a small txn: INGESTION → GUARDRAIL → LINK → LLM/FALLBACK → DISPATCH.
5. **Guardrail wow:** ₹7.5k did **not** auto-send. Click Approve.
6. **₹25k:** Accept only if you want a live call; else Decline and explain no auto-dial.
7. **WhatsApp:** dual-script + `/pay/` link. Tap → Recovered on dashboard.
8. **What broke:** HMAC, SQLite locks, Twilio `twiml=` trial 400, localhost WhatsApp links, `.env` not loaded. Point at `BUILD_LOG.md`.

---

## 20. What broke (honest engineering)

Use 2–3 of these:

| Failure | Lesson |
|---|---|
| WhatsApp `127.0.0.1` is plain text / hits the phone | Need a **public HTTPS** origin |
| `rzp.io` click does not update our DB | Evidence must hit **our** `/pay` or paid webhook |
| Twilio trial rejects inline TwiML | Fallback **Twimlets URL** |
| Commit before WhatsApp send | Avoid SQLite lock on live send |
| After unloading `.env`, Green API skipped | Local gitignored `.env` still needed for demo |
| loca.lt interstitial | Prefer **trycloudflare** |
| Simulator auto-RECOVERED before click | Live mode leaves DISPATCHED until tap |

**Sentence:** *We journaled failures in BUILD_LOG.md instead of hiding them.*

---

## 21. Design choices they will attack

**Why FastAPI not Node?** Python for LLM + Razorpay SDK + pytest; one language for agent + guards.

**Why SQLite?** Demo/hackathon. Swap `DATABASE_URL` to Postgres; SQLAlchemy stays.

**Why GPT-4o-mini?** Latency, JSON mode, cost, Indian language. Fallback if the API is down.

**Why Green API not Meta Cloud?** Faster to a personal number without WhatsApp Business template approval. Production would use official Cloud API + templates.

**Is the 72% recovery fake?** In **tests**, simulator marks ~72% of sub-₹5k as recovered to prove metrics. **Live demo** waits for a real `/pay` click. Say both.

**Is voice “recovered” without collecting money?** Demo **simulates authorized high-value recovery** after merchant Accept + call placed. Production would wait for `payment_link.paid`.

**Why dual-script?** Accessibility: users who read Kannada/Tamil/Hindi **and** users who only read Latin (Kanglish/Tanglish).

---

## 22. If this went to production

- PostgreSQL, queues (Redis/Celery) for send, not request-thread Green API.
- Official WhatsApp Cloud API + template IDs.
- Secrets in vault, not `.env`.
- Idempotent webhook inbox (event id unique).
- Real Razorpay paid webhook URL on a stable domain (not trycloudflare).
- Fine-tuned classifier locally; LLM only for copy.
- Rate limits, merchant multi-tenancy, PCI: we never store PAN/CVV (only gateway ids).

---

## 23. Numbers to memorize

| Number | Meaning |
|---|---|
| 15–20% | Typical India payment fail rate |
| ₹5,000 | Auto-WhatsApp cap |
| ₹20,000 | Voice permission; no auto-dial |
| 2 | Max outreach retries |
| 0.75 | Min LLM confidence |
| 202 | Failed webhook accepted |
| 401 | Bad HMAC |
| 3s | Dashboard refresh |
| ~46 | pytest count (say “full pytest suite”) |

---

## 24. Rapid-fire Q&A

**What is RecoverPay AI?**  
An event-driven engine that turns Razorpay `payment.failed` into guarded, localized 1-click recovery, with an audit trail and dashboard metrics.

**Where is the agent?**  
`backend/agent.py` + pipeline in `main.py`. Not a chat UI.

**What is a guardrail?**  
A hard rule in Python that the LLM cannot skip.

**How do you stop prompt injection in names?**  
`sanitize_text` strips control chars and blocks “ignore previous instructions” style names.

**How do you know the LLM didn’t change the link?**  
`payment_link in message` after parse; else fallback template.

**What’s in an audit log?**  
Step name, success/fail, optional LLM prompt/response, guardrail JSON, timing.

**How is recovery rate computed?**  
Recovered ÷ (recovered + still dispatched).

**What happens if OpenAI is down?**  
Regional templates, `used_fallback=true`, still dispatch if guardrails pass.

**How do you handle STOP?**  
WhatsApp webhook / registry; next ingest → `OPTED_OUT`.

**Why HMAC on raw body?**  
Canonical JSON may not match the signed bytes.

**What’s TEST_MODE?**  
Forces templates, skips live WhatsApp/Twilio; pytest sets it.

**Show me the 5k rule in one sentence.**  
If amount &gt; 5000, status is FLAGGED_FOR_APPROVAL and we do not send WhatsApp until a human approves.

**Show me the 20k rule.**  
If amount &gt; 20000, we do not dial until the merchant clicks Accept.

**What’s the pay URL?**  
`GET /pay/{transaction_id}` on a public HTTPS host.

---

## 25. Closing line

*RecoverPay AI is not “ChatGPT on a dashboard.” It is a hybrid recovery control plane: LLMs write the message, Python owns money, retries, consent, and cryptographic trust — and every step is auditable.*

---

*Study this plus a live click-through of Simulate 20 → Inspect Audit → Approve / Voice banner → `/pay` click. That combination cracks a buildathon panel.*
