from __future__ import annotations
from datetime import datetime
from difflib import SequenceMatcher
from time import perf_counter

def _money(v):
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None

def _date(v):
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v))
    except ValueError:
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(str(v), fmt)
            except ValueError:
                pass
    return None

def _days(a, b):
    da, db = _date(a), _date(b)
    if not da or not db:
        return 999
    return abs((da - db).days)

def _sim(a, b):
    return SequenceMatcher(None, str(a or "").lower(), str(b or "").lower()).ratio()

def reconcile(orders, gateways, banks):
    started = perf_counter()

    gateways_by_order = {str(x.get("order_id", "")): x for x in gateways if x.get("order_id")}
    banks_by_gateway = {str(x.get("gateway_id", "")): x for x in banks if x.get("gateway_id")}

    used_gateway_ids = set()
    used_bank_ids = set()
    results = []

    for order in orders:
        oid = str(order.get("order_id", ""))
        gate = gateways_by_order.get(oid)

        if not gate:
            candidates = [
                g for g in gateways
                if g.get("gateway_id") not in used_gateway_ids
                and _money(g.get("amount")) == _money(order.get("amount"))
                and _days(g.get("date"), order.get("date")) <= 2
            ]
            if candidates:
                gate = max(
                    candidates,
                    key=lambda g: (
                        _sim(g.get("description"), order.get("description")),
                        -_days(g.get("date"), order.get("date"))
                    ),
                )

        gateway_id = str(gate.get("gateway_id", "")) if gate else ""
        bank = banks_by_gateway.get(gateway_id) if gateway_id else None

        # A bank transaction can still be matched by amount/date when its gateway reference is absent.
        if not bank and gate:
            candidates = [
                b for b in banks
                if b.get("bank_id") not in used_bank_ids
                and _money(b.get("amount")) == _money(gate.get("amount"))
                and _days(b.get("date"), gate.get("date")) <= 3
            ]
            if candidates:
                bank = min(candidates, key=lambda b: _days(b.get("date"), gate.get("date")))

        order_amount = _money(order.get("amount"))
        gateway_amount = _money(gate.get("amount")) if gate else None
        bank_amount = _money(bank.get("amount")) if bank else None

        signals = []
        confidence = 0.0
        status = "UNRESOLVED"
        reason = ""
        exception_type = ""
        severity = ""
        recommended = ""
        amount_at_risk = 0.0

        if not gate:
            status = "UNRESOLVED"
            exception_type = "MISSING_PAYMENT"
            severity = "HIGH"
            confidence = 0.05
            reason = "No payment-gateway record could be confidently linked to this order."
            recommended = "Verify whether the payment was captured and inspect the gateway settlement batch."
            amount_at_risk = order_amount or 0.0
        elif not bank:
            status = "NEEDS_REVIEW"
            exception_type = "MISSING_SETTLEMENT"
            severity = "HIGH"
            confidence = 0.30
            signals = ["order↔gateway linked", "gateway↔bank link missing"]
            reason = "The order and gateway payment are linked, but no bank settlement could be confidently found."
            recommended = "Check the bank settlement file and gateway payout/settlement report."
            amount_at_risk = gateway_amount or order_amount or 0.0
            used_gateway_ids.add(gateway_id)
        else:
            used_gateway_ids.add(gateway_id)
            used_bank_ids.add(str(bank.get("bank_id", "")))

            date_ok = _days(gate.get("date"), bank.get("date")) <= 3
            amount_diff = round((bank_amount or 0.0) - (gateway_amount or 0.0), 2)
            desc_score = _sim(gate.get("description"), bank.get("description"))

            if order.get("order_id") and gate.get("order_id") == oid:
                signals.append("order_id exact")
                confidence += 0.45
            if gateway_id and bank.get("gateway_id") == gateway_id:
                signals.append("gateway_id exact")
                confidence += 0.35
            if gateway_amount is not None and bank_amount is not None and abs(amount_diff) <= 0.01:
                signals.append("amount exact")
                confidence += 0.15
            elif gateway_amount is not None and bank_amount is not None:
                signals.append("amount differs")
            if date_ok:
                signals.append("settlement date within 3 days")
                confidence += 0.05
            if desc_score >= 0.75:
                signals.append(f"description similarity {round(desc_score*100)}%")

            if gateway_amount is not None and bank_amount is not None and abs(amount_diff) >= 0.01:
                status = "NEEDS_REVIEW"
                exception_type = "AMOUNT_MISMATCH"
                severity = "HIGH" if abs(amount_diff) >= max(100, (gateway_amount or 0) * 0.05) else "MEDIUM"
                confidence = min(0.97, max(confidence, 0.65))
                reason = f"Gateway amount ₹{gateway_amount:,.2f} differs from bank settlement ₹{bank_amount:,.2f} by ₹{amount_diff:,.2f}."
                recommended = "Review fees, partial settlement, refunds, chargebacks, or missing adjustments."
                amount_at_risk = abs(amount_diff)
            elif confidence >= 0.85:
                status = "MATCHED"
                confidence = min(confidence, 0.99)
                reason = "Order, payment and settlement references align within configured amount/date tolerances."
            elif confidence >= 0.55:
                status = "PROBABLE_MATCH"
                confidence = min(confidence, 0.89)
                exception_type = "PROBABLE_MATCH_REVIEW"
                severity = "MEDIUM"
                reason = "Records align on several signals but lack enough evidence for an automatic match."
                recommended = "Spot-check the payment reference before closing the item."
                amount_at_risk = 0.0
            else:
                status = "NEEDS_REVIEW"
                exception_type = "UNRESOLVED_MATCH"
                severity = "MEDIUM"
                confidence = min(confidence, 0.49)
                reason = "Available identifiers and financial signals are insufficient for a safe automatic match."
                recommended = "Review the source records and settlement reference manually."
                amount_at_risk = bank_amount or gateway_amount or order_amount or 0.0

        results.append({
            "record_kind": "ORDER",
            "order_id": oid,
            "gateway_id": gateway_id,
            "bank_id": str(bank.get("bank_id", "")) if bank else "",
            "order_amount": order_amount,
            "gateway_amount": gateway_amount,
            "bank_amount": bank_amount,
            "order_date": str(order.get("date", "")),
            "gateway_date": str(gate.get("date", "")) if gate else "",
            "bank_date": str(bank.get("date", "")) if bank else "",
            "status": status,
            "confidence": round(confidence, 4),
            "reason": reason,
            "signals": signals,
            "exception_type": exception_type,
            "severity": severity,
            "recommended_action": recommended,
            "amount_at_risk": round(amount_at_risk, 2),
        })

    # Surface orphan gateway and bank rows as explicit operational exceptions.
    for g in gateways:
        gid = str(g.get("gateway_id", ""))
        if gid not in used_gateway_ids and not g.get("order_id"):
            amt = _money(g.get("amount")) or 0.0
            results.append({
                "record_kind": "GATEWAY_ONLY",
                "order_id": "",
                "gateway_id": gid,
                "bank_id": "",
                "order_amount": None,
                "gateway_amount": amt,
                "bank_amount": None,
                "order_date": "",
                "gateway_date": str(g.get("date", "")),
                "bank_date": "",
                "status": "UNRESOLVED",
                "confidence": 0.0,
                "reason": "Payment-gateway record has no order reference and could not be linked safely.",
                "signals": ["gateway-only"],
                "exception_type": "GATEWAY_ONLY_TRANSACTION",
                "severity": "MEDIUM",
                "recommended_action": "Trace the payment reference back to the order or gateway settlement batch.",
                "amount_at_risk": amt,
            })

    for b in banks:
        bid = str(b.get("bank_id", ""))
        if bid not in used_bank_ids and not b.get("gateway_id"):
            amt = _money(b.get("amount")) or 0.0
            results.append({
                "record_kind": "BANK_ONLY",
                "order_id": "",
                "gateway_id": "",
                "bank_id": bid,
                "order_amount": None,
                "gateway_amount": None,
                "bank_amount": amt,
                "order_date": "",
                "gateway_date": "",
                "bank_date": str(b.get("date", "")),
                "status": "UNRESOLVED",
                "confidence": 0.0,
                "reason": "Bank transaction has no gateway reference and could not be linked safely.",
                "signals": ["bank-only"],
                "exception_type": "BANK_ONLY_TRANSACTION",
                "severity": "HIGH",
                "recommended_action": "Trace the settlement reference and verify whether the bank line belongs to a merchant payout.",
                "amount_at_risk": amt,
            })

    elapsed = perf_counter() - started
    return results, elapsed
