# PAYSHIELD AI

**Let AI decide. Let PAYSHIELD authorize.**

PAYSHIELD AI is a hackathon prototype for an AI-assisted payment security gateway. It evaluates proposed payments against deterministic spending policies, analyzes untrusted invoice text with an optional Gemini integration, and can create PayPal Sandbox checkout orders for transactions that pass policy.

## Important prototype boundaries

- This is a hackathon demonstration, not a production fraud-detection or payment-security product.
- The deterministic policy engine is authoritative. AI output is advisory and can never approve a payment or lower the policy risk score.
- The in-memory audit log and invoice history reset when the server restarts. Use a persistent database before production.
- PayPal checkout is sandbox-only. A transaction that passes PAYSHIELD still requires the payer to approve the PayPal checkout.
- Never put API secrets in frontend code or commit `.env`.

## Features

- ALLOW / REVIEW / BLOCK policy decisions
- Per-transaction spending limit
- Approved-vendor allowlist
- Duplicate invoice detection (current server session)
- Prompt-injection marker detection in invoice text
- Optional Gemini invoice analysis
- PayPal Orders API sandbox order creation
- Attack simulator and audit dashboard
- Unit tests for core policy rules

## Requirements

- Python 3.10+
- PayPal Developer account and Sandbox REST app credentials for checkout
- Optional Gemini API key for model-based invoice analysis

## Run locally (Windows PowerShell)

```powershell
py -3 -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env and add your sandbox credentials / optional Gemini key
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000

API docs: http://127.0.0.1:8000/docs

## Run tests

```powershell
pytest -q
```

## PayPal Sandbox setup

1. Sign in at https://developer.paypal.com/
2. Open Apps & Credentials and choose Sandbox.
3. Create a REST app or use a sandbox app.
4. Copy its Client ID and Secret into `.env`.
5. Keep `PAYPAL_MODE=sandbox`.
6. In the app, evaluate an ALLOW transaction and click **Create PayPal Sandbox checkout**.
7. Complete payer approval in the PayPal Sandbox browser flow.

The API creates an order but does not silently capture funds. The capture endpoint is intentionally separate and must only be called after the payer has approved the order.

### API endpoints

- `GET /api/health`
- `GET /api/policy`
- `POST /api/evaluate`
- `GET /api/decisions`
- `GET /api/audit`
- `POST /api/paypal/create-order/{decision_id}`
- `POST /api/paypal/capture/{order_id}`

Example request:

```json
{
  "vendor": "ABC Technologies",
  "amount": 8500,
  "currency": "USD",
  "invoice_id": "INV-2026-001",
  "invoice_text": "Invoice for approved equipment."
}
```

## Demo scenarios

Use the Attack Simulator buttons in the UI:
- Prompt injection
- Amount manipulation
- Unknown supplier
- Duplicate invoice
- Legitimate payment

Expected results:
- Injection: BLOCK
- Amount above $10,000 limit: BLOCK
- Unknown supplier: REVIEW
- Duplicate invoice ID: BLOCK
- Approved vendor within limit: ALLOW

## Architecture

1. Frontend sends a proposed transaction to FastAPI.
2. Optional Gemini analysis inspects invoice text as untrusted data.
3. Deterministic policy engine enforces limits, supplier allowlist, duplicates and prompt-injection markers.
4. Only `ALLOW` decisions can request a PayPal Sandbox order.
5. Payer approves at PayPal; payment capture is a separate server-side operation.
6. Every evaluation and payment event is shown in the audit trail.

## Roadmap before production

- Persistent PostgreSQL database and immutable audit events
- Tenant-specific policy management, roles and approvals
- Strong supplier identity verification and bank-account change controls
- Currency conversion and cumulative daily/monthly limits
- Idempotency, webhook signature verification and reconciliation
- Robust invoice OCR and structured extraction with human confirmation
- Threat-model review, security testing and compliance assessment

## License

MIT. See `LICENSE`.
