# RecoverPay AI — 5-Minute Loom Teleprompter

**Read only the spoken lines.**  
Anything in `[BRACKETS]` is a stage direction. Do not say it out loud.

**Pace:** about **120 words per minute** of speech, plus pauses for clicks.  
If the timer hits **4:30** before the close, skip the “what broke” story and jump to the closing paragraph.

---

## 0. Do this 10 minutes before you hit Record

1. Close Slack, email, extra Chrome tabs. Hide bookmarks. Zoom the browser to **110%**.
2. Start the app with `run.bat`. Open **http://localhost:8000**.
3. Prefer **dark theme** (click `☀️ Light` so it becomes dark — looks more “product”).
4. Do **one practice Simulate 20**. Note:
   - one **amber** row (₹7,500-ish) → you will Approve this
   - one **rose / red** row (₹25,000) + left **voice banner** → you will **Decline**
   - one **RECOVERY_DISPATCHED** row with **Confirm payment** → you will click this
5. For a clean take: stop the server, delete `recoverpay.db` in the project folder, run `run.bat` again so cards show **₹0.00**. Then **do not** simulate until the camera is rolling.
6. Loom: **Screen + Cam**. Cam small, **bottom-left**. Mouse **large**. Speak to the camera in the hook and the close; look at the screen in the middle.
7. **Do not** click `Accept & Place AI Voice Call` on camera (phone may ring and wreck the take). **Decline** is the hero moment.
8. **Do not** open `.env`. **Do not** say “Next.js”. The live UI is FastAPI + this dashboard.
9. Optional: keep WhatsApp open on your phone. If a dual-script message arrived, flash the phone at the webcam for **3 seconds**. If it didn’t, ignore the phone — **Confirm payment** is the same proof.

Put this file on a **second monitor**, zoom **150%**, and scroll as you talk.

---

## 1. What you show (shot list)

| Time | On screen | You do |
|---|---|---|
| 0:00–0:40 | Full dashboard, metrics at ₹0 | Face the camera. Do not click yet. |
| 0:40–1:10 | Same dashboard, slowly pan cards → funnel | Point with the mouse. No click. |
| 1:10–1:50 | Top-right **Simulate 20 Failed Payments** | Click once. Wait. Scroll the table. |
| 1:50–2:40 | Amber row + left **voice banner** | Approve one amber row. **Decline** the voice call. |
| 2:40–3:35 | **Inspect Audit** drawer (+ phone preview if it opens) | Click Inspect Audit on a small dispatched row. Scroll steps. Close. |
| 3:35–4:20 | **Confirm payment** → `/pay` page → back to dashboard | Click Confirm payment. Tab back. Wait 3s. Point at **RECOVERED**. |
| 4:20–5:00 | Metrics cards + your face | Bank widget optional. Close on camera. |

---

# TELEPROMPTER — START READING HERE

---

## [ 0:00 – 0:40 ]  HOOK

Hi.

I’m [YOUR NAME].

This is RecoverPay AI.

Built for the Razorpay AI Buildathon, 2026.

Track 03. AI Revenue Recovery.

In India, fifteen to twenty percent of checkouts fail at the last step.

Bank timeout.

Low balance.

OTP drop.

Merchants send a generic email the next day.

Almost nobody comes back.

That is revenue leakage.

On one crore rupees of monthly GMV, that is fifteen to thirty lakh rupees leaking every month.

---

## [ 0:40 – 1:10 ]  WHAT THIS IS

**[MOVE MOUSE slowly across the four top cards, then the funnel. Do not click.]**

RecoverPay AI is not a chatbot.

It is an event-driven recovery engine.

When Razorpay fires payment.failed, three things happen.

First, we verify the webhook with HMAC SHA256 on the raw body.

Bad signature. HTTP 401. We never trust the JSON until the signature is valid.

Second, a Python guardrail state machine decides if we are allowed to speak.

The LLM cannot override that.

Third, GPT-4o-mini writes a regional WhatsApp message with a one-click pay link.

When the customer taps that link, status moves from Recovery Dispatched to Recovered.

This is the live merchant dashboard.

FastAPI backend. SQLite. Full audit trail.

Phones on screen are masked. We never touch cards. Razorpay owns checkout.

---

## [ 1:10 – 1:50 ]  SIMULATE 20

**[CLICK the blue button, top right: Simulate 20 Failed Payments]**

**[WAIT 4 seconds. Do not talk over the first second.]**

I’m ingesting twenty failed payments, the way a Razorpay webhook batch would hit us.

**[POINT at Total Failed Volume, then the funnel bars]**

Watch the cards.

Failed volume jumps.

The funnel fills.

At risk.

AI diagnosed.

Policy approved.

Action executed.

Recovered.

**[SCROLL the transaction table slowly]**

Look at the table.

Small amounts went to Recovery Dispatched. WhatsApp already left.

Amber rows are above five thousand rupees. They did not auto-send.

And this rose row is above twenty thousand.

The system is asking the merchant for permission.

It will not auto-dial.

---

## [ 1:50 – 2:40 ]  THE WOW — GUARDRAILS

This is the part I want you to remember.

We did not let GPT decide if twelve thousand rupees is safe.

Large language models hallucinate.

Money is policy.

Policy belongs in code.

Three hard rules. In this order.

One. Opt-out registry. If the customer said STOP, we never message.

Two. Retry cap of two. Then Max Retries Reached. Hard stop.

Three. Amount above five thousand. Status becomes Flagged for Approval.

Never auto-dispatch.

**[CLICK 🚨 Approve & Send (>₹5K) on ONE amber row only]**

**[WAIT 2 seconds]**

I just approved one flagged order.

WhatsApp is now allowed.

The LLM still only writes copy.

Python still owns the money.

**[POINT at the left voice banner: HIGH-VALUE FAILURE]**

For twenty-five thousand rupees, a silent WhatsApp is not enough.

The merchant must Accept before we place a Twilio voice call.

I am going to Decline.

That proves the agent is bounded.

**[CLICK ❌ Decline Call]**

**[WAIT 1 second]**

Status is now Voice Call Declined.

No call. No spam. Merchant stayed in control.

---

## [ 2:40 – 3:35 ]  INSPECT AUDIT + THE AI

**[CLICK Inspect Audit on a small RECOVERY_DISPATCHED row — not the ₹25k row]**

**[WAIT for the drawer / phone preview]**

This is the execution trace.

Every financial action is logged.

Ingestion.

Guardrail check.

Payment link generation.

LLM diagnosis — or a fallback template if confidence is below zero point seven five.

Then Dispatch.

GPT-4o-mini classifies the failure.

Temporary outage. Insufficient funds. Auth failed. User drop-off.

Then it writes dual-script WhatsApp.

Kannada, then Kanglish.

Tamil, then Tanglish.

Hindi, then Hinglish.

English stays one block.

The model must paste the payment link character for character.

If it changes the URL, we throw the output away and use a template.

That is structured generation with a schema gate.

Not a free-form chatbot.

**[If the 3D phone is visible, POINT at the message for 2 seconds. If WhatsApp arrived on your real phone, hold it to the webcam for 3 seconds. Otherwise skip.]**

**[CLOSE the audit drawer]**

---

## [ 3:35 – 4:20 ]  CLICK = RECOVERED

A Razorpay short link is clickable.

But RecoverPay would never see the tap.

The dashboard would stay Recovery Dispatched forever.

So we send our own public URL.

Slash pay, slash transaction id.

When the customer opens it, we write Payment Evidence Confirmed.

And we mark Recovered.

There is a second path. Razorpay payment_link.paid. Same HMAC check.

**[CLICK Confirm payment on a RECOVERY_DISPATCHED row]**

**[The /pay page opens. Leave it 1 second.]**

Customer just tapped the WhatsApp link.

**[SWITCH BACK to the dashboard tab]**

**[WAIT 3 seconds — the table refreshes by itself]**

Watch the pill.

Recovery Dispatched becomes Recovered.

**[POINT at Recovered Revenue, then Recovery Rate %]**

Recovered revenue ticks up.

Recovery rate is recovered count, divided by recovered plus still dispatched.

We do not dilute that number with the twenty-five thousand rupee row sitting in review.

That is measured recovery.

Not a mocked percentage on a slide.

---

## [ 4:20 – 5:00 ]  WHAT BROKE + CLOSE

**[Optional: POINT at the Bank Health tab on the right for 2 seconds. Do not click Simulate SBI unless you have 15 seconds spare.]**

Two things that broke, because this was real engineering.

First. Localhost in WhatsApp is not a blue link.

And on a phone, 127.0.0.1 is the phone, not my laptop.

So we expose public HTTPS, and the tap hits RecoverPay.

Second. Twilio trial rejected inline TwiML.

We fell back to a Twimlets URL.

It’s written in BUILD_LOG.md.

We journal failures. We don’t hide them.

If this went to production: Postgres. A job queue. Official WhatsApp Cloud API. A stable webhook domain.

We would still never auto-dispatch above five thousand.

We would still never auto-dial above twenty thousand.

**[LOOK AT THE CAMERA]**

RecoverPay AI is not ChatGPT on a dashboard.

It is a hybrid recovery control plane.

LLMs write the message.

Python owns money, retries, consent, and cryptographic trust.

And every step is auditable.

Thank you.

---

# TELEPROMPTER — STOP

---

## 2. If something goes wrong on camera (say this, keep rolling)

| What happens | Say this | Do this |
|---|---|---|
| Simulate is slow | “The batch is hitting guardrails one row at a time.” | Wait. Do not click twice. |
| No WhatsApp on phone | “Live send is optional. The proof is the Confirm payment URL hitting our server.” | Click Confirm payment. |
| `/pay` page looks plain | “That page is the evidence endpoint. The dashboard is about to flip.” | Switch back. Wait 3s. |
| Voice banner missing | “Voice permission only appears for amounts above twenty thousand.” | Scroll the table for the rose row. |
| You clicked Accept by mistake | “That’s the authorized high-value path. Twilio would now ring the customer.” | Do not panic. Continue to Inspect Audit. |
| You are at 4:30 and still in audit | Skip “what broke”. Jump to “RecoverPay AI is not ChatGPT…” | Close on camera. |
| Metrics already had old data | “I’m adding a fresh batch on top of the live ledger.” | Still click Simulate 20. |

---

## 3. Words you should say vs words you should not say

**Say**
- event-driven recovery engine
- hybrid agent
- deterministic Python guardrails
- HMAC SHA256 on the raw body
- bounded agency
- dual-script WhatsApp
- one-click `/pay` evidence

**Do not say**
- “It’s just a chatbot”
- “Next.js” (we did not ship Next.js)
- “100 payments, 74% recovered” unless those numbers are on *your* screen
- any live API keys, full phone numbers, or `.env`

---

## 4. After you stop recording

Watch the take once at **1.5x**. You only re-record if:
- you never showed **Flagged / Decline voice**
- you never showed **Recovery Dispatched → Recovered**
- the hook or the close is mumbled

Title the Loom something like:

`RecoverPay AI — 5 min demo | Razorpay Buildathon Track 03`

First-comment / description (paste under the video):

```
RecoverPay AI — Track 03 AI Revenue Recovery
Failed Razorpay payments → HMAC webhook → Python guardrails (₹5k / ₹20k / 2 retries / opt-out) → GPT-4o-mini dual-script WhatsApp → 1-click /pay evidence → RECOVERED.
Hybrid agent: LLM writes copy. Python owns money, consent, and cryptographic trust.
```
