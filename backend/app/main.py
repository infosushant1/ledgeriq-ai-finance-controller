from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from .db import Base, SessionLocal, engine
from .models import AuditEvent, ExceptionRecord, Transaction
from .services.ai import explain
from .services.metrics import build_metrics
from .services.reconciliation import reconcile

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "generated"
DATA.mkdir(parents=True, exist_ok=True)
DIST = ROOT / "frontend" / "dist"
RUN_METRICS = DATA / "run_metrics.json"

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="LedgerIQ — AI Finance Controller",
    version="3.0.0",
    description="Explainable multi-source reconciliation with exception intelligence and audit workflow.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)

class ReviewRequest(BaseModel):
    status: str

def add_audit(db, action, details, transaction_id=None, exception_id=None, actor="SYSTEM"):
    db.add(AuditEvent(
        transaction_id=transaction_id,
        exception_id=exception_id,
        action=action,
        actor=actor,
        details=details,
    ))

def read_csv(name: str):
    path = DATA / name
    if not path.exists():
        raise HTTPException(400, f"{name} is missing. Generate demo data or upload the required CSV.")
    return pd.read_csv(path).fillna("")

def validate_csvs():
    required = {
        "orders.csv": {"order_id", "date", "amount", "description"},
        "payment_gateway.csv": {"gateway_id", "order_id", "date", "amount", "description"},
        "bank_transactions.csv": {"bank_id", "gateway_id", "date", "amount", "description"},
    }
    for name, cols in required.items():
        df = read_csv(name)
        missing = cols - set(df.columns)
        if missing:
            raise HTTPException(400, f"{name} missing columns: {sorted(missing)}")

def persist_results(results):
    db = SessionLocal()
    try:
        db.execute(delete(ExceptionRecord))
        db.execute(delete(Transaction))
        db.execute(delete(AuditEvent))
        db.commit()

        for x in results:
            tx = Transaction(
                order_id=x["order_id"],
                gateway_id=x["gateway_id"],
                bank_id=x["bank_id"],
                order_amount=x["order_amount"],
                gateway_amount=x["gateway_amount"],
                bank_amount=x["bank_amount"],
                order_date=x["order_date"],
                gateway_date=x["gateway_date"],
                bank_date=x["bank_date"],
                status=x["status"],
                confidence=x["confidence"],
                reason=x["reason"],
                signals=json.dumps(x["signals"]),
                exception_type=x["exception_type"],
                severity=x["severity"],
                amount_at_risk=x["amount_at_risk"],
                review_status="OPEN",
            )
            db.add(tx)
            db.flush()

            if x["exception_type"]:
                priority = 95 if x["severity"] == "HIGH" else 70
                priority += min(5, round(x["amount_at_risk"] / 10000, 2))
                priority = min(100, round(priority, 2))
                ex = ExceptionRecord(
                    transaction_id=tx.id,
                    order_id=x["order_id"] or x["gateway_id"] or x["bank_id"],
                    exception_type=x["exception_type"],
                    severity=x["severity"],
                    expected_amount=x["gateway_amount"] if x["exception_type"] == "AMOUNT_MISMATCH" else (x["order_amount"] or x["gateway_amount"]),
                    actual_amount=x["bank_amount"],
                    difference=(round((x["bank_amount"] or 0) - (x["gateway_amount"] or 0), 2)
                                if x["exception_type"] == "AMOUNT_MISMATCH" else None),
                    confidence=x["confidence"],
                    amount_at_risk=x["amount_at_risk"],
                    priority_score=priority,
                    explanation=x["reason"],
                    recommended_action=x["recommended_action"],
                )
                db.add(ex)
                db.flush()
                add_audit(
                    db,
                    "EXCEPTION_CREATED",
                    f"{x['exception_type']} | risk ₹{x['amount_at_risk']:,.2f} | confidence {x['confidence']:.0%}",
                    transaction_id=tx.id,
                    exception_id=ex.id,
                )
            else:
                add_audit(
                    db,
                    "RECONCILED",
                    f"{x['status']} | confidence {x['confidence']:.0%} | signals: {', '.join(x['signals']) or 'none'}",
                    transaction_id=tx.id,
                )

        db.commit()
    finally:
        db.close()

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "ledgeriq", "version": "3.0.0"}

@app.post("/api/generate-demo")
def generate_demo():
    script = ROOT / "scripts" / "generate_dataset.py"
    try:
        subprocess.run([sys.executable, str(script)], check=True, capture_output=True, text=True)
        return {"message": "Demo dataset generated.", "files": ["orders.csv", "payment_gateway.csv", "bank_transactions.csv", "ground_truth.csv"]}
    except subprocess.CalledProcessError as exc:
        raise HTTPException(500, exc.stderr or exc.stdout or "Dataset generation failed.")
    except FileNotFoundError as exc:
        raise HTTPException(500, f"Python executable could not be started: {exc}")

@app.post("/api/upload")
async def upload(
    orders: UploadFile = File(...),
    payment_gateway: UploadFile = File(...),
    bank_transactions: UploadFile = File(...),
):
    allowed = {"orders.csv", "payment_gateway.csv", "bank_transactions.csv"}
    for upload_file in (orders, payment_gateway, bank_transactions):
        if Path(upload_file.filename or "").name not in allowed:
            raise HTTPException(400, "Use exactly orders.csv, payment_gateway.csv and bank_transactions.csv.")
        content = await upload_file.read()
        if len(content) > 10_000_000:
            raise HTTPException(413, "CSV too large.")
        (DATA / Path(upload_file.filename).name).write_bytes(content)
    return {"message": "CSV files uploaded successfully."}

@app.post("/api/reconcile")
def run_reconcile():
    validate_csvs()
    orders = read_csv("orders.csv").to_dict("records")
    gateways = read_csv("payment_gateway.csv").to_dict("records")
    banks = read_csv("bank_transactions.csv").to_dict("records")
    truth = read_csv("ground_truth.csv").to_dict("records") if (DATA / "ground_truth.csv").exists() else []

    results, elapsed = reconcile(orders, gateways, banks)
    persist_results(results)

    metrics = build_metrics(results, truth)
    metrics["processing_time_seconds"] = round(elapsed, 6)
    metrics["throughput_records_per_second"] = round(len(results) / elapsed, 2) if elapsed else 0.0
    metrics["source_counts"] = {
        "orders": len(orders),
        "payment_gateway": len(gateways),
        "bank_transactions": len(banks),
    }
    RUN_METRICS.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics

@app.get("/api/summary")
def summary():
    db = SessionLocal()
    try:
        rows = db.query(Transaction).all()
        truth = read_csv("ground_truth.csv").to_dict("records") if (DATA / "ground_truth.csv").exists() else []
        data = [{
            "status": r.status,
            "exception_type": r.exception_type,
            "amount_at_risk": r.amount_at_risk,
            "order_id": r.order_id,
        } for r in rows]
        result = build_metrics(data, truth)
        if RUN_METRICS.exists():
            try:
                saved = json.loads(RUN_METRICS.read_text(encoding="utf-8"))
                for key in ("processing_time_seconds", "throughput_records_per_second", "source_counts"):
                    if key in saved:
                        result[key] = saved[key]
            except Exception:
                pass
        audit_count = db.query(AuditEvent).count()
        result["audit_events"] = audit_count
        result["engine_status"] = "online"
        return result if rows else {"total_records": 0, "engine_status": "online"}
    finally:
        db.close()

@app.get("/api/transactions")
def transactions():
    db = SessionLocal()
    try:
        rows = db.query(Transaction).order_by(Transaction.id.desc()).all()
        return [{
            "id": r.id,
            "order_id": r.order_id,
            "gateway_id": r.gateway_id,
            "bank_id": r.bank_id,
            "order_amount": r.order_amount,
            "gateway_amount": r.gateway_amount,
            "bank_amount": r.bank_amount,
            "status": r.status,
            "confidence": r.confidence,
            "reason": r.reason,
            "signals": json.loads(r.signals or "[]"),
            "exception_type": r.exception_type,
            "severity": r.severity,
            "amount_at_risk": r.amount_at_risk,
            "review_status": r.review_status,
        } for r in rows]
    finally:
        db.close()

@app.get("/api/transactions/{tid}")
def transaction_detail(tid: int):
    db = SessionLocal()
    try:
        r = db.query(Transaction).filter(Transaction.id == tid).first()
        if not r:
            raise HTTPException(404, "Transaction not found.")
        events = db.query(AuditEvent).filter(AuditEvent.transaction_id == tid).order_by(AuditEvent.id.desc()).all()
        return {
            "transaction": {
                "id": r.id, "order_id": r.order_id, "gateway_id": r.gateway_id, "bank_id": r.bank_id,
                "order_amount": r.order_amount, "gateway_amount": r.gateway_amount, "bank_amount": r.bank_amount,
                "order_date": r.order_date, "gateway_date": r.gateway_date, "bank_date": r.bank_date,
                "status": r.status, "confidence": r.confidence, "reason": r.reason,
                "signals": json.loads(r.signals or "[]"), "exception_type": r.exception_type,
                "severity": r.severity, "amount_at_risk": r.amount_at_risk, "review_status": r.review_status,
            },
            "audit": [{
                "action": e.action, "actor": e.actor, "details": e.details,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            } for e in events],
        }
    finally:
        db.close()

@app.get("/api/exceptions")
def exceptions():
    db = SessionLocal()
    try:
        rows = db.query(ExceptionRecord).order_by(ExceptionRecord.priority_score.desc(), ExceptionRecord.id.desc()).all()
        return [{
            "id": r.id, "transaction_id": r.transaction_id, "order_id": r.order_id,
            "exception_type": r.exception_type, "severity": r.severity,
            "expected_amount": r.expected_amount, "actual_amount": r.actual_amount,
            "difference": r.difference, "confidence": r.confidence,
            "amount_at_risk": r.amount_at_risk, "priority_score": r.priority_score,
            "explanation": r.explanation, "recommended_action": r.recommended_action,
            "review_status": r.review_status,
        } for r in rows]
    finally:
        db.close()

@app.get("/api/exceptions/{eid}")
def exception_detail(eid: int):
    db = SessionLocal()
    try:
        e = db.query(ExceptionRecord).filter(ExceptionRecord.id == eid).first()
        if not e:
            raise HTTPException(404, "Exception not found.")
        tx = db.query(Transaction).filter(Transaction.id == e.transaction_id).first() if e.transaction_id else None
        events = db.query(AuditEvent).filter(AuditEvent.exception_id == eid).order_by(AuditEvent.id.desc()).all()
        return {
            "exception": {
                "id": e.id, "transaction_id": e.transaction_id, "order_id": e.order_id,
                "exception_type": e.exception_type, "severity": e.severity,
                "expected_amount": e.expected_amount, "actual_amount": e.actual_amount,
                "difference": e.difference, "confidence": e.confidence,
                "amount_at_risk": e.amount_at_risk, "priority_score": e.priority_score,
                "explanation": e.explanation, "recommended_action": e.recommended_action,
                "review_status": e.review_status,
            },
            "transaction": {
                "id": tx.id if tx else None,
                "order_id": tx.order_id if tx else e.order_id,
                "gateway_id": tx.gateway_id if tx else "",
                "bank_id": tx.bank_id if tx else "",
                "order_amount": tx.order_amount if tx else None,
                "gateway_amount": tx.gateway_amount if tx else None,
                "bank_amount": tx.bank_amount if tx else None,
                "signals": json.loads(tx.signals or "[]") if tx else [],
            },
            "audit": [{
                "action": a.action, "actor": a.actor, "details": a.details,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            } for a in events],
        }
    finally:
        db.close()

@app.post("/api/exceptions/{eid}/review")
def review(eid: int, body: ReviewRequest):
    if body.status not in {"APPROVED", "REJECTED", "OPEN"}:
        raise HTTPException(400, "Status must be APPROVED, REJECTED or OPEN.")
    db = SessionLocal()
    try:
        e = db.query(ExceptionRecord).filter(ExceptionRecord.id == eid).first()
        if not e:
            raise HTTPException(404, "Exception not found.")
        e.review_status = body.status
        tx = db.query(Transaction).filter(Transaction.id == e.transaction_id).first() if e.transaction_id else None
        if tx:
            tx.review_status = body.status
        add_audit(db, "HUMAN_REVIEW", f"Exception {eid} changed to {body.status}.", tx.id if tx else None, e.id, "REVIEWER")
        db.commit()
        return {"status": body.status}
    finally:
        db.close()

@app.post("/api/exceptions/{eid}/ai-explain")
async def ai_explain(eid: int):
    db = SessionLocal()
    try:
        e = db.query(ExceptionRecord).filter(ExceptionRecord.id == eid).first()
        if not e:
            raise HTTPException(404, "Exception not found.")
        tx = db.query(Transaction).filter(Transaction.id == e.transaction_id).first() if e.transaction_id else None
        context = {
            "exception": {
                "type": e.exception_type, "expected": e.expected_amount,
                "actual": e.actual_amount, "difference": e.difference,
                "confidence": e.confidence,
            },
            "transaction": {
                "order_id": tx.order_id if tx else e.order_id,
                "gateway_id": tx.gateway_id if tx else "",
                "bank_id": tx.bank_id if tx else "",
                "order_amount": tx.order_amount if tx else None,
                "gateway_amount": tx.gateway_amount if tx else None,
                "bank_amount": tx.bank_amount if tx else None,
            },
        }
        result = await explain(context)
        add_audit(db, "AI_EXPLANATION", f"Provider: {result.get('provider', 'unknown')}.", tx.id if tx else None, e.id, "AI")
        db.commit()
        return result
    finally:
        db.close()

@app.post("/api/chat")
def chat(req: ChatRequest):
    q = req.question.lower()
    db = SessionLocal()
    try:
        tx = db.query(Transaction).all()
        ex = db.query(ExceptionRecord).all()
        total = len(tx)
        matched = sum(x.status in {"MATCHED", "PROBABLE_MATCH"} for x in tx)
        review = sum(x.status == "NEEDS_REVIEW" for x in tx)
        unresolved = sum(x.status == "UNRESOLVED" for x in tx)
        risk = sum(x.amount_at_risk or 0 for x in tx if x.status not in {"MATCHED", "PROBABLE_MATCH"})
        breakdown = {}
        for e in ex:
            breakdown[e.exception_type] = breakdown.get(e.exception_type, 0) + 1

        if "amount at risk" in q or "risk" in q or "money" in q:
            answer = f"₹{risk:,.2f} is currently at risk across {len(ex)} exception records."
        elif "most" in q and ("exception" in q or "issue" in q):
            top = max(breakdown.items(), key=lambda x: x[1]) if breakdown else ("none", 0)
            answer = f"The most frequent exception is {top[0].replace('_', ' ').title()} with {top[1]} records."
        elif "unresolved" in q:
            answer = f"There are {unresolved} unresolved records."
        elif "matched" in q or "reconciled" in q:
            answer = f"{matched} of {total} processed records are matched or probable matches."
        elif "review" in q:
            answer = f"{review} records currently need human review."
        elif "exception" in q:
            answer = f"There are {len(ex)} exception records. The current risk exposure is ₹{risk:,.2f}."
        elif "rate" in q or "percentage" in q:
            rate = (matched / total * 100) if total else 0
            answer = f"The current match/probable rate is {rate:.2f}%."
        else:
            answer = f"The batch contains {total} records: {matched} matched/probable, {review} needing review and {unresolved} unresolved. Amount at risk is ₹{risk:,.2f}."

        add_audit(db, "COPILOT_QUERY", req.question, actor="COPILOT")
        db.commit()
        return {"answer": answer, "grounded": True}
    finally:
        db.close()

@app.get("/api/audit")
def audit(limit: int = 100):
    limit = max(1, min(limit, 500))
    db = SessionLocal()
    try:
        rows = db.query(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit).all()
        return [{
            "id": r.id, "transaction_id": r.transaction_id, "exception_id": r.exception_id,
            "action": r.action, "actor": r.actor, "details": r.details,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        } for r in rows]
    finally:
        db.close()

@app.get("/api/report")
def report():
    db = SessionLocal()
    try:
        rows = db.query(Transaction).all()
        ex = db.query(ExceptionRecord).all()
        audit = db.query(AuditEvent).count()
        truth = read_csv("ground_truth.csv").to_dict("records") if (DATA / "ground_truth.csv").exists() else []
        data = [{
            "status": r.status, "exception_type": r.exception_type,
            "amount_at_risk": r.amount_at_risk, "order_id": r.order_id
        } for r in rows]
        metrics = build_metrics(data, truth)
        metrics["audit_events"] = audit
        metrics["exceptions"] = [{
            "order_id": e.order_id, "type": e.exception_type, "severity": e.severity,
            "amount_at_risk": e.amount_at_risk, "priority_score": e.priority_score,
            "review_status": e.review_status,
        } for e in ex]
        return metrics
    finally:
        db.close()

# Serve the production frontend if it has been built.
if DIST.exists():
    @app.get("/{path:path}")
    def spa(path: str):
        candidate = DIST / path
        return FileResponse(candidate if candidate.is_file() else DIST / "index.html")
