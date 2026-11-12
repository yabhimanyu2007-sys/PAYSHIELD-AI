from __future__ import annotations
import os
from unittest import result
from unittest import result
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.services.policy_engine import DEFAULT_POLICY, evaluate_transaction
from app.services.ai_analyzer import analyze_invoice_with_ai
from app.services.paypal_service import create_order, capture_order

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT.parent / ".env")

app = FastAPI(
    title="PAYSHIELD AI",
    description="AI-assisted payment security firewall. AI advises; deterministic policy authorizes.",
    version="0.1.0"
)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

DECISIONS: dict[str, dict[str, Any]] = {}
AUDIT_LOG: list[dict[str, Any]] = []
SEEN_INVOICES: set[str] = {"DEMO-DUPLICATE-001"}

class TransactionRequest(BaseModel):
    vendor: str = Field(min_length=1, max_length=120)
    amount: float = Field(gt=0, le=100000000)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    invoice_id: str = Field(min_length=1, max_length=100)
    invoice_text: str = Field(default="", max_length=12000)
    description: str = Field(default="Supplier payment", max_length=300)

class PolicyUpdate(BaseModel):
    max_transaction: float = Field(gt=0, le=100000000)
    daily_limit: float = Field(gt=0, le=1000000000)
    approved_vendors: list[str] = Field(min_length=1, max_length=50)

def log_event(event: dict[str, Any]) -> None:
    AUDIT_LOG.insert(0, event)
    del AUDIT_LOG[200:]

@app.get("/")
def home():
    return FileResponse(ROOT / "static" / "index.html")

@app.get("/api/health")
def health():
    return {"status": "ok", "project": "PAYSHIELD AI", "version": "0.1.0"}

@app.get("/api/policy")
def get_policy():
    return DEFAULT_POLICY

@app.post("/api/evaluate")
def evaluate(request: TransactionRequest):
    payload = request.model_dump()
    ai_result = analyze_invoice_with_ai(request.invoice_text)
    print("SENTINAL AI RESULTS:",ai_result)
    prior = set(SEEN_INVOICES)
    result = evaluate_transaction(payload, DEFAULT_POLICY, prior)
    # Sentinel AI risk integration.
    # ==========================================
    # PAYSHIELD SENTINEL AI RISK INTEGRATION
    # ==========================================

    # 1. Safely extract AI risk score
    try:
        ai_score = int(ai_result.get("risk_score", 0) or 0)
    except (TypeError, ValueError):
        ai_score = 0

    ai_score = max(0, min(100, ai_score))

    # 2. Extract AI findings and recommendation
    ai_findings = ai_result.get("findings", [])

    if not isinstance(ai_findings, list):
        ai_findings = []

    ai_action = str(
        ai_result.get("recommended_action", "")
    ).upper()

    suspicious_instruction = bool(
        ai_result.get("suspicious_instruction", False)
    )

    # 3. Preserve the highest risk score
    policy_score = int(result.get("risk_score", 0) or 0)

    result["risk_score"] = max(
        policy_score,
        ai_score
    )

    # 4. Store AI analysis for dashboard and audit
    result["ai_risk_score"] = ai_score
    result["ai_risk_level"] = ai_result.get(
        "risk_level", "UNKNOWN"
    )
    result["ai_findings"] = ai_findings
    result["ai_explanation"] = ai_result.get(
        "explanation", ""
    )

    # 5. Determine whether AI has detected a serious threat
    ai_high_risk = (
        ai_score >= 80
        or ai_action in ("REJECT", "BLOCK")
        or suspicious_instruction
    )

    # 6. AI can escalate ALLOW to REVIEW, never approve.
    current_decision = str(
        result.get("decision", "")
    ).upper()

    if current_decision == "BLOCK":
        result["payment_authorized"] = False

    elif current_decision == "ALLOW" and ai_high_risk:

        result["decision"] = "REVIEW"
        result["payment_authorized"] = False

        result.setdefault("findings", []).append({
            "code": "AI_SENTINEL_ALERT",
            "severity": "high",
            "message": (
                "Sentinel AI detected suspicious invoice activity. "
                "Human review is required."
            )
        })

    # 7. Preserve deterministic REVIEW decisions
    elif current_decision == "REVIEW":
        result["payment_authorized"] = False


    decision_id = str(uuid.uuid4())
    record = {
        "id": decision_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        **payload,
        **result,
        "ai_analysis": ai_result,
        "paypal_order_id": None,
        "payment_status": "NOT_STARTED"
    }
    DECISIONS[decision_id] = record
    if request.invoice_id:
        SEEN_INVOICES.add(request.invoice_id)
    log_event({
        "id": decision_id,
        "time": record["created_at"],
        "vendor": request.vendor,
        "amount": request.amount,
        "currency": request.currency.upper(),
        "decision": result["decision"],
        "risk_score": result["risk_score"],
        "event": "PAYMENT_EVALUATED"
    })
    return record

@app.get("/api/decisions")
def list_decisions():
    return list(DECISIONS.values())[:100]

@app.get("/api/audit")
def audit():
    return AUDIT_LOG[:100]

@app.post("/api/paypal/create-order/{decision_id}")
def paypal_create(decision_id: str):
    record = DECISIONS.get(decision_id)
    if not record:
        raise HTTPException(404, "Decision not found.")
    if record["decision"] != "ALLOW" or not record["payment_authorized"]:
        raise HTTPException(403, "PAYSHIELD policy did not authorize this transaction.")
    if record.get("paypal_order_id"):
        raise HTTPException(409, "A PayPal order already exists for this decision.")
    try:
        order = create_order(record["amount"], record["currency"], decision_id)
    except Exception as exc:
        raise HTTPException(502, f"PayPal order creation failed: {str(exc)[:300]}")
    record["paypal_order_id"] = order.get("id")
    record["payment_status"] = "AWAITING_PAYER_APPROVAL"
    record["paypal_approve_url"] = next(
        (link["href"] for link in order.get("links", []) if link.get("rel") == "approve"),
        None
    )
    log_event({
        "id": decision_id, "time": datetime.now(timezone.utc).isoformat(),
        "vendor": record["vendor"], "amount": record["amount"],
        "currency": record["currency"], "decision": "ALLOW",
        "risk_score": record["risk_score"], "event": "PAYPAL_ORDER_CREATED"
    })
    return {"order_id": order.get("id"), "status": order.get("status"),
            "approve_url": record["paypal_approve_url"]}

@app.post("/api/paypal/capture/{order_id}")
def paypal_capture(order_id: str):
    record = next((r for r in DECISIONS.values() if r.get("paypal_order_id") == order_id), None)
    if not record:
        raise HTTPException(404, "No PAYSHIELD decision is associated with this order.")
    if record["decision"] != "ALLOW":
        raise HTTPException(403, "Transaction is not authorized.")
    try:
        result = capture_order(order_id)
    except Exception as exc:
        raise HTTPException(502, f"PayPal capture failed: {str(exc)[:300]}")
    record["payment_status"] = result.get("status", "UNKNOWN")
    record["paypal_capture_result"] = result
    log_event({
        "id": record["id"], "time": datetime.now(timezone.utc).isoformat(),
        "vendor": record["vendor"], "amount": record["amount"],
        "currency": record["currency"], "decision": record["decision"],
        "risk_score": record["risk_score"], "event": "PAYPAL_CAPTURE_" + record["payment_status"]
    })
    return {"order_id": order_id, "status": record["payment_status"]}

@app.get("/payment/success")
def payment_success():
    return FileResponse(ROOT / "static" / "payment-success.html")

@app.get("/payment/cancel")
def payment_cancel():
    return FileResponse(ROOT / "static" / "payment-cancel.html")
