# RecoverPay AI — Product Specification & Master Buildathon Blueprint

**Project Title**: RecoverPay AI  
**Track**: Track 03 — AI Revenue Recovery  
**Target Event**: Razorpay AI Buildathon 2026  
**Role Target**: AI Builder Intern (₹75,000 / month, Bangalore HQ)  
**Tagline**: Autonomous Payment Recovery Engine with Financial Guardrails & Live Execution Auditing  

---

## Executive Summary & Foundational Overview

### Q1. What is the Razorpay AI Buildathon?
The Razorpay AI Buildathon is a student-only hiring initiative by Razorpay designed to recruit their next cohort of **AI Builder Interns** (₹75,000/month stipend, 6 or 12-month duration, in-person at Bangalore HQ). Unlike conventional campus placement drives, it bypasses CGPA shortlisting, resume filters, aptitude tests, and group discussions. Candidates are evaluated purely on proof-of-work: shipping a functional AI system, publishing a public GitHub repository, delivering a 5-minute pitch video, and explaining system architecture and failure recovery.

### Q2. What are the challenge tracks available?
The Buildathon features 5 challenge tracks:
1. **Track 01: AI Growth & Agentic Commerce** (Autonomous buying agents, merchant revenue growth)
2. **Track 02: AI Risk Manager** (Defense-only fraud detection and risk reporting)
3. **Track 03: AI Revenue Recovery** (Payment drop-off, mandate retries, Hinglish voice/SMS recovery)
4. **Track 04: AI Finance Controller** (Reconciliation, expense automation, financial operations)
5. **Track 05: Open Track** (Any AI-native innovation outside the core four)

### Q3. What is the offer, stipend, duration, and key dates?
* **Stipend**: ₹75,000 / month
* **Duration**: 6 or 12 months (Candidate's choice)
* **Location**: In-person at Razorpay HQ, Bengaluru from September 2026
* **Application Deadline**: September 5, 2026
* **Official Link**: `https://razorpay.com/buildathon/`

### Q4. What are the required submission deliverables?
Applicants must submit 12 specific details on the portal:
1. Full Name
2. College Name
3. Graduation Year (2027–2030 batches)
4. Availability for Bangalore starting September
5. Duration choice (6 vs 12 months)
6. Resume File (for background context)
7. Selected Track (Track 03: AI Revenue Recovery)
8. Project Name (*RecoverPay AI*)
9. Problem & Solution Summary
10. Public GitHub Repository URL (containing clean code, `README.md`, and test suite)
11. 5-Minute Pitch Video Link (Unlisted Loom/YouTube showing live demo and architecture)
12. "What Broke & How You Got Out" Narrative (Technical post-mortem of a real issue solved)

### Q5. What is the selection process from build to offer?
The workflow is completely meritocratic:
`[ Pick Track ] ➔ [ Build & Ship Prototype ] ➔ [ Submit Repo + Pitch Video ] ➔ [ Direct Technical Panel Review ] ➔ [ Internship Offer ]`

---

## Part 1: Problem Definition & Market Opportunity

### Q6. What exactly is the problem we are solving?
**Payment & Revenue Leakage in Digital Commerce.**  
In modern online checkout flows and recurring subscription systems, **15% to 30% of payment transactions fail or get abandoned** before completion. Existing solutions handle failures via static, unpersonalized emails sent 24 hours later, leading to permanent revenue loss and wasted customer acquisition costs (CAC).

### Q7. What is the official Buildathon problem statement/challenge?
**Track 03: AI Revenue Recovery**
* *Challenge Prompt*: *"Payment degradation → root cause → recovery action, Checkout drop-off recovery, Failed-subscription recovery, B2B receivables chaser, Mandate retry sequencer, Hinglish voice recovery, Promise-to-pay tracker."*
* *The Standard ("The Bar")*: *"Don’t just identify the problem. Show measured money recovered across a batch, with compliant escalation, stopping rules, and an audit trail."*

### Q8. What are the explicit requirements and constraints?
* **Root-Cause Analysis**: Parse payment failure payload logs (e.g., `BAD_REQUEST_PAYMENT_TIMED_OUT`, `INSUFFICIENT_FUNDS`) and diagnose the root cause.
* **Autonomous Action**: Trigger dynamic, localized recovery outreach (Hinglish WhatsApp/SMS with single-click Razorpay Payment Links).
* **Batch Recovery Proof**: Process a batch of mock/simulated transactions (100 payments) and calculate exact **% Money Recovered** vs. **Outreach Cost**.
* **Financial Guardrails**: Enforce bounded execution (max 2 outreach retries, human escalation caps over ₹5,000, instant opt-out compliance).
* **Audit Trail**: Maintain an immutable execution log recording every prompt, LLM reasoning step, tool call, and API response.

### Q9. Who exactly experiences this problem?
1. **Merchants & Businesses (Primary Users)**: D2C E-commerce brands, SaaS platforms with recurring subscriptions, and B2B companies with outstanding receivables.
2. **End Consumers (Secondary Users)**: Shoppers whose payment failed due to bank server timeouts, expired cards, or temporary friction who still wish to complete the purchase.

### Q10. What is the user's current workflow for solving it?
Currently, when a customer attempts checkout:
`[ Payment Fails ] ➔ [ Gateway Returns Error Code ] ➔ [ Static Email Sent 24 Hrs Later ] ➔ [ 0-5% Conversion / User Ignores ]`
Merchants rely on generic billing plugins that send cold English emails long after the user has left the checkout funnel.

### Q11. What are the biggest pain points in the current workflow?
* **Zero Context Awareness**: Identical generic emails sent regardless of whether failure was a bank timeout vs. an invalid card vs. low balance.
* **Wrong Channel & Delay**: Email open rates in India are <15%, whereas WhatsApp open rates exceed 90%. Delaying outreach by hours destroys intent.
* **No Localized Persuasion**: Communication lacks conversational warmth or regional language support (Hinglish).
* **Unbounded Risk**: Simple scripts can spam users or issue unauthorized discounts without spending caps.

### Q12. How frequently does this problem occur?
* **Daily Baseline**: Payment failure rates average **15% to 20%** across Indian payment gateways.
* **Peak Sale Events**: During flash sales, festival shopping, or major bank server maintenance windows, payment degradation spikes to **35% - 40%**.

### Q13. What is the measurable impact of this problem?
* **Revenue Loss**: A business processing ₹1 Crore/month loses **₹15 Lakhs to ₹30 Lakhs monthly** to failed checkout payments.
* **Ad Spend Destruction**: CAC spent acquiring the customer (ad clicks, marketing) is incinerated when checkout drops off at the final step.

### Q14. Why is this problem worth solving NOW?
* **Agentic AI + LLM Speed**: High-speed LLMs (GPT-4o-mini, Claude) can analyze structured log payloads and generate localized messaging in sub-seconds.
* **Razorpay's Strategic Focus**: Razorpay is transitioning towards AI-native financial products. Solving revenue recovery directly matches their product roadmap.

### Q15. What happens if this problem is not solved?
Merchants suffer a permanent 20% top-line drag, consumers experience checkout frustration, and payment gateways lose transaction processing volume (MDR).

---

## Part 2: Competitive Analysis & Technical Differentiation

### Q16. What existing products already solve this problem?
The global market category is **Involuntary Churn & Payment Dunning Software**. Key global players include *Stripe Smart Retries*, *FlyCode*, *Butter Payments*, *Slicker*, *Recurflux*, *Churnkey*, *Churn Buster*, and *Baremetrics Recover*.

### Q17. What are the closest competitors?
In India and the Razorpay ecosystem:
1. **Gateway Silent Retries** (Default Razorpay/Stripe automated retry background algorithms).
2. **Traditional Email Dunning Plugins** (Chargebee / Recurflux automated email flows).
3. **Outcraft AI / Gravy** (AI & human call-center outreach services).

### Q18. How do their solutions work?
* Silent Retries attempt charging credit cards again 24–72 hours later.
* Email Dunning triggers a standard templated email requesting updated billing info.
* Rule Engines execute basic `if/else` logic based on decline codes.

### Q19. What are their weaknesses or limitations?
* **Email Bias**: Reliance on email fails in India where messaging apps (WhatsApp) dominate.
* **No UPI / Mandate Optimization**: Built for US credit cards; unable to handle India-specific UPI Intent, Auto-Pay mandates, or Instant Payment Links.
* **Black-Box Retries**: Gateway silent retries offer zero merchant visibility into why retries failed.
* **Lack of Safety Guardrails**: Vulnerable to run-away LLM behavior or un-capped discount generation.

### Q20. What existing APIs, SDKs, and open-source tools can we leverage?
* **Razorpay Python/Node SDK**: For issuing Payment Links (`/v1/payment_links`) and handling Webhook events (`payment.failed`).
* **FastAPI (Python) & Next.js 14**: Backend REST service and frontend dashboard.
* **OpenAI GPT-4o-mini / Vercel AI SDK**: Structured diagnosis and Hinglish copy generation.
* **SQLite + SQLAlchemy**: Persistent audit trail and metrics store.
* **Recharts & Tailwind CSS**: Modern interactive analytics dashboard UI.

### Q21. What percentage of our proposed solution is genuinely differentiated?
**40% Core Technical Differentiation**:
* **60% Standard Stack**: Webhooks, DB storage, LLM APIs, Next.js UI.
* **40% Unique Engine**:
  1. *India-First Agentic Channel Flow* (Localized Hinglish WhatsApp + UPI Payment Links).
  2. *Deterministic Financial State Machine* (Bounded retries, human approval caps >₹5,000, opt-out handling).
  3. *Live Execution Audit Graph* (Visual node-by-node tracing of prompts, tool calls, and financial decisions).

### Q22. Why would a user choose our solution instead of an existing product?
1. **3x Higher Conversion**: Instant WhatsApp outreach + UPI single-click payment links.
2. **Zero Code Migration**: Plugs into existing Razorpay Webhooks in <5 minutes.
3. **Guaranteed Safety**: Bounded state machine guarantees no unauthorized transactions or spam.

### Q23. Why would a Razorpay engineer/judge consider this technically interesting?
1. **Demonstrates AI Judgment**: Hybrid architecture combining probabilistic LLMs (reasoning) with deterministic guardrails (financial limits).
2. **Production-Ready Security**: Immutable audit log and graceful error fallback handling.
3. **Direct ROI Metrics**: Proves exact money recovered across simulated test batches.

---

## Part 3: Product Blueprint & User Experience

### Q24. What exactly are we building?
**RecoverPay AI**: An autonomous, agentic payment recovery engine for Razorpay merchants that intercepts payment failure webhooks, diagnoses root causes, generates localized WhatsApp recovery messages with dynamic Razorpay Payment Links, and logs every step in a live audit trail.

### Q25. What is the one-sentence description of the product?
> *"RecoverPay AI automatically recovers failed Razorpay checkout payments and subscriptions via localized WhatsApp recovery agents, bounded by strict financial guardrails and real-time audit logs."*

### Q26. What is the primary user persona?
**SaaS Founders, E-Commerce Merchants, & Growth Engineers** using Razorpay in India who want to reduce checkout drop-offs and subscription churn automatically.

### Q27. What is the complete user journey from opening the product to getting the result?
1. **Dashboard Overview**: Merchant views top-line stats (*Total Failed Volume*, *Recovered Revenue*, *Recovery Rate %*, *Outreach Cost*).
2. **Trigger Event**: A live Razorpay test webhook arrives or merchant clicks *"Simulate 100 Failed Transactions"*.
3. **Agent Diagnosis**: System reads the failure code (`BAD_REQUEST_PAYMENT_TIMED_OUT`) and selects the recovery strategy.
4. **Guardrail Check**: System verifies: `amount < ₹5,000`? `retries < 2`? `user_opt_out == False`?
5. **Action**: Dynamic Razorpay Payment Link generated and sent via Hinglish WhatsApp sandbox.
6. **Audit Verification**: Merchant inspects the visual execution graph in the **Audit Log**.

### Q28. What is the single most important feature?
**The Bounded Recovery Workflow Engine**: The hybrid core that pairs LLM diagnostic reasoning with hard-coded Python safety guardrails.

### Q29. What is our "WOW" feature for the demo?
**The Interactive Live Audit Trail & Visual Execution Graph**:
In the demo video, clicking any transaction opens a step-by-step execution node graph showing:
`Event Received ➔ LLM Diagnosis ➔ Guardrail Check (Cap Triggered) ➔ Human Approval Step ➔ Executed Recovery Link`.

### Q30. What are the absolute minimum features required for the MVP?
1. Metric Summary Cards (Failed Volume, Recovered Amount, Recovery Rate %).
2. Razorpay API Link Generation (`/v1/payment_links`).
3. LLM Diagnostic & Hinglish Copy Generator.
4. Hard-Coded Guardrail Gate (`amount > 5000` approval trigger, max 2 retries).
5. Audit Log Table with trace details.
6. Batch Simulator button (10-50 mock payments).

### Q31. Which features should we deliberately NOT build? (Out of Scope)
* ❌ Custom billing software (use Razorpay APIs).
* ❌ Real WhatsApp Meta Business API onboarding (use sandbox/mock logger).
* ❌ Complex multi-tenant authentication.

### Q32. What should happen in the ideal successful scenario?
1. Payment fails on Razorpay test mode (`BAD_REQUEST_PAYMENT_TIMED_OUT`).
2. Webhook triggers RecoverPay AI in <200ms.
3. Agent crafts Hinglish WhatsApp draft with a dynamic UPI Payment Link.
4. Safety checks pass; message is sent.
5. Customer pays via link; system receives `payment_link.paid` webhook.
6. Dashboard updates status to `RECOVERED` and updates net ROI.

### Q33. What should happen when something goes wrong? (Error Handling & Fallbacks)
* **LLM Output Error**: Fallback to a pre-defined deterministic recovery template and log `LLM_FALLBACK_TRIGGERED`.
* **Razorpay API Downtime**: Queue payload with exponential backoff (max 3 retries).
* **Customer Opt-Out**: Immediate trigger sets `opt_out = True` in DB and halts all future communication.

---

## Part 4: Vibecoding & Agentic Engineering Setup

### Recommended Directory Structure
```
/recoverpay-ai
├── AGENTS.md                 # Agentic coding rules & guardrails for Cursor/Windsurf
├── BUILD_LOG.md              # Live debugging & error resolution journal
├── product_specification.md  # Master 33-question product specification document
├── backend/
│   ├── main.py               # FastAPI server entry point
│   ├── razorpay_client.py    # Razorpay SDK helper (/v1/payment_links)
│   ├── agent.py              # LLM diagnostic & copy generator
│   ├── guardrails.py         # Financial bounds & stopping rules engine
│   └── database.py           # SQLite audit log & transaction store
└── frontend/
    ├── app/                  # Next.js 14 App Router (Dashboard, Audit Log, Simulator)
    ├── components/           # UI Components (Metrics, Node Graph, Audit Table)
    └── lib/                  # API client & types
```

---
*Document compiled and verified for the Razorpay AI Buildathon 2026.*
