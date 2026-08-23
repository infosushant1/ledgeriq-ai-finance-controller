import os
import json
import httpx
from dotenv import load_dotenv

load_dotenv()

def local_explanation(context):
    ex = context.get("exception", {})
    tx = context.get("transaction", {})
    typ = ex.get("type", "UNRESOLVED")
    expected = ex.get("expected")
    actual = ex.get("actual")
    diff = ex.get("difference")
    order_id = tx.get("order_id") or "source-only transaction"

    mapping = {
        "MISSING_PAYMENT": (
            "No gateway payment was confidently linked to the order.",
            "Verify capture status and inspect the gateway payment/settlement batch."
        ),
        "MISSING_SETTLEMENT": (
            "The gateway payment exists, but no bank settlement was confidently linked.",
            "Compare the gateway payout report with the bank settlement file."
        ),
        "AMOUNT_MISMATCH": (
            f"The gateway and bank amounts differ by ₹{abs(diff or 0):,.2f}.",
            "Check fees, partial settlement, refund, chargeback, or adjustment lines."
        ),
        "BANK_ONLY_TRANSACTION": (
            "A bank line has no gateway reference, so it cannot be safely attributed.",
            "Trace the settlement reference to the gateway payout batch."
        ),
        "GATEWAY_ONLY_TRANSACTION": (
            "A gateway line has no order reference, so the payment cannot be safely attributed.",
            "Trace the payment reference back to the merchant order."
        ),
    }
    explanation, action = mapping.get(
        typ,
        ("The available source signals are insufficient for an automatic close.", "Review the source records and settlement reference.")
    )
    return {
        "provider": "deterministic-finance-reasoner",
        "answer": (
            f"{order_id}: {explanation} "
            f"Expected ₹{expected:,.2f} and actual ₹{actual:,.2f}."
            if expected is not None and actual is not None
            else f"{order_id}: {explanation}"
        ),
        "recommended_action": action,
        "confidence": round(float(ex.get("confidence") or 0), 2),
        "grounded": True,
    }

async def explain(context):
    api_key = os.getenv("AI_API_KEY", "").strip()
    base_url = os.getenv("AI_BASE_URL", "").strip().rstrip("/")
    model = os.getenv("AI_MODEL", "").strip()

    if not (api_key and base_url and model):
        return local_explanation(context)

    prompt = f"""
You are a finance-operations copilot. Explain the reconciliation exception below.
Use only the supplied facts. Do not invent transactions or amounts.
Return concise JSON with keys: answer, recommended_action, risk_note.
Context:
{json.dumps(context, default=str)}
"""
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "temperature": 0.1,
                    "messages": [
                        {"role": "system", "content": "You are an audit-conscious finance operations assistant."},
                        {"role": "user", "content": prompt},
                    ],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                parsed = {"answer": content, "recommended_action": "Review the source records.", "risk_note": "AI output was not JSON."}
            parsed["provider"] = "external-llm"
            parsed["grounded"] = True
            return parsed
    except Exception:
        result = local_explanation(context)
        result["provider"] = "deterministic-fallback"
        result["risk_note"] = "External AI was unavailable; deterministic explanation used."
        return result
