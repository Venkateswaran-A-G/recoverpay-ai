"""Customer-facing Confirm / Decline pages for WhatsApp /pay/{id} links."""

from __future__ import annotations

from html import escape

from fastapi.responses import HTMLResponse

_CSS = """
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body {
  margin: 0;
  min-height: 100vh;
  font-family: Sora, ui-sans-serif, system-ui, sans-serif;
  background: #080a0f;
  color: #f8fafc;
  display: grid;
  place-items: center;
  padding: 24px 16px;
}
.card {
  width: min(420px, 100%);
  background: rgba(15, 23, 42, 0.72);
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 20px;
  padding: 28px 22px 22px;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.45);
}
.brand {
  font-size: 12px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #7dd3fc;
  font-weight: 700;
  margin: 0 0 18px;
}
h1 { font-size: 22px; margin: 0 0 8px; font-weight: 650; }
.amount { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 28px; margin: 12px 0 8px; }
.muted { color: #94a3b8; font-size: 14px; line-height: 1.5; margin: 0 0 22px; }
.actions { display: grid; gap: 10px; }
button, .btn {
  display: block;
  width: 100%;
  text-align: center;
  text-decoration: none;
  border: 0;
  border-radius: 12px;
  padding: 14px 16px;
  font: inherit;
  font-size: 16px;
  font-weight: 650;
  cursor: pointer;
}
.confirm { background: linear-gradient(180deg, #34d399, #059669); color: #06281d; }
.decline { background: rgba(244, 63, 94, 0.16); color: #fecdd3; border: 1px solid rgba(244, 63, 94, 0.4); }
.ok { color: #6ee7b7; }
.warn { color: #fda4af; }
"""


def _shell(title: str, inner: str, *, public_base: str | None = None) -> HTMLResponse:
    base_tag = ""
    if public_base:
        base_tag = f'<base href="{escape(public_base.rstrip("/"))}/"/>'
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  {base_tag}
  <title>{escape(title)}</title>
  <style>{_CSS}</style>
</head>
<body>
  <main class="card">
    <p class="brand">RecoverPay AI</p>
    {inner}
  </main>
</body>
</html>"""
    return HTMLResponse(html)


def choice_page(
    *,
    transaction_id: str,
    customer_name: str | None,
    amount: str,
    public_base: str,
) -> HTMLResponse:
    name = escape((customer_name or "there").split()[0])
    tid = escape(transaction_id)
    origin = escape(public_base.rstrip("/"))
    inner = f"""
    <h1>Hi {name}</h1>
    <p class="amount">₹{escape(amount)}</p>
    <p class="muted">This payment did not go through. Confirm if you completed it, or decline if you do not want recovery messages.</p>
    <div class="actions">
      <a class="btn confirm" href="{origin}/pay/{tid}/confirm">Confirm</a>
      <a class="btn decline" href="{origin}/pay/{tid}/decline">Decline</a>
    </div>
    """
    return _shell("Confirm or decline payment", inner, public_base=public_base)


def recovered_page(*, already: bool = False) -> HTMLResponse:
    headline = "Already recovered" if already else "Recovered"
    copy = (
        "This order was already marked RECOVERED. Thank you."
        if already
        else "Thank you. RecoverPay AI marked this order RECOVERED."
    )
    inner = f"""
    <h1 class="ok">{escape(headline)}</h1>
    <p class="muted">{escape(copy)}</p>
    """
    return _shell(headline, inner)


def opted_out_page(*, already: bool = False) -> HTMLResponse:
    headline = "Already opted out" if already else "Opted out"
    copy = (
        "You are already on the opt-out list. We will not send more recovery messages."
        if already
        else "Understood. This order is OPTED_OUT. We will not message you again about this payment."
    )
    inner = f"""
    <h1 class="warn">{escape(headline)}</h1>
    <p class="muted">{escape(copy)}</p>
    """
    return _shell(headline, inner)


def status_page(message: str) -> HTMLResponse:
    inner = f'<h1>Cannot update this payment</h1><p class="muted">{escape(message)}</p>'
    return _shell("Cannot update this payment", inner)
