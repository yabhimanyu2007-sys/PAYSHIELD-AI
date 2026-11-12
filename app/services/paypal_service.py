from __future__ import annotations
import os
import requests

def _base_url() -> str:
    mode = os.getenv("PAYPAL_MODE", "sandbox").lower()
    return "https://api-m.sandbox.paypal.com" if mode != "live" else "https://api-m.paypal.com"

def _access_token() -> str:
    client_id = os.getenv("PAYPAL_CLIENT_ID")
    secret = os.getenv("PAYPAL_CLIENT_SECRET")
    if not client_id or not secret:
        raise RuntimeError("PayPal credentials are not configured. Add sandbox credentials to .env.")
    response = requests.post(
        f"{_base_url()}/v1/oauth2/token",
        auth=(client_id, secret),
        data={"grant_type": "client_credentials"},
        headers={"Accept": "application/json"},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()["access_token"]

def create_order(amount: float, currency: str = "USD", reference_id: str = "PAYSHIELD-DEMO") -> dict:
    if os.getenv("PAYPAL_MODE", "sandbox").lower() == "live":
        raise RuntimeError("Live payments are disabled in this hackathon build. Use PayPal Sandbox.")
    token = _access_token()
    response = requests.post(
        f"{_base_url()}/v2/checkout/orders",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
        json={
            "intent": "CAPTURE",
            "purchase_units": [{
                "reference_id": reference_id,
                "description": "PAYSHIELD AI approved demo payment",
                "amount": {"currency_code": currency.upper(), "value": f"{amount:.2f}"}
            }],
            "payment_source": {
                "paypal": {
                    "experience_context": {
                        "brand_name": "PAYSHIELD AI",
                        "user_action": "PAY_NOW",
                        "return_url": os.getenv("PAYPAL_RETURN_URL", "http://127.0.0.1:8000/payment/success"),
                        "cancel_url": os.getenv("PAYPAL_CANCEL_URL", "http://127.0.0.1:8000/payment/cancel")
                    }
                }
            }
        },
        timeout=25,
    )
    response.raise_for_status()
    return response.json()

def capture_order(order_id: str) -> dict:
    if os.getenv("PAYPAL_MODE", "sandbox").lower() == "live":
        raise RuntimeError("Live payments are disabled in this hackathon build. Use PayPal Sandbox.")
    token = _access_token()
    response = requests.post(
        f"{_base_url()}/v2/checkout/orders/{order_id}/capture",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={},
        timeout=25,
    )
    response.raise_for_status()
    return response.json()
