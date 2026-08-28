# LedgerIQ — AI Finance Controller

AI-powered finance operations controller for reconciliation, exception management, and finance intelligence.

### 👉 [Open LedgerIQ Live Demo](https://ledgeriq-ai-finance-controller-demo.onrender.com)

## 📄 Project Presentation

[📥 View Project Presentation](./docs/iq3.pdf)

## What it does

LedgerIQ closes one finance-ops loop:

**Orders → Payment Gateway → Bank Settlement → Reconciliation → Exceptions → AI explanation → Human review → Audit trail**

It is intentionally hybrid:

- Deterministic rules handle money-critical matching.
- AI is optional and used for explanations/recommendations and grounded copilot queries.
- Every unresolved item remains visible instead of being silently forced into a match.
- Metrics include match rate, validation precision/recall/F1, processing time and throughput.
- The dashboard exposes amount at risk and exception priority.

## Features

1. Demo data generator with 200+ source records.
2. CSV upload for orders, gateway and bank files.
3. Exact and soft matching using IDs, amounts, dates and description similarity.
4. Explicit exception types:
   - Missing payment
   - Missing settlement
   - Amount mismatch
   - Bank-only transaction
   - Gateway-only transaction
   - Unresolved match
5. Amount-at-risk calculation.
6. Exception breakdown and priority score.
7. Detailed decision evidence for every transaction.
8. Finance Copilot grounded in the current database.
9. Optional OpenAI-compatible LLM integration with deterministic fallback.
10. Human approve/reject/re-open workflow.
11. Audit trail for reconciliation, exceptions, AI explanations, copilot queries and human review.
12. Production frontend served by FastAPI after `npm run build`.

## 🚀 Live Demo

### 👉 [Open LedgerIQ Live Demo](https://ledgeriq-ai-finance-controller-demo.onrender.com)

**No installation required. Open the link and start testing.**

> Note: The Render free instance may take up to ~50 seconds to wake after inactivity.

### Recommended demo flow

1. Open the Live Demo
2. Click **Demo Data**
3. Click **Run Reconciliation**
4. Review reconciliation metrics
5. Open **Exceptions**
6. Inspect an exception
7. Ask **Finance Copilot** questions
8. Review the **Audit Trail**
9. Upload custom CSV data and run another reconciliation
 
## Current verified package versions

As of August 2026 this project pins FastAPI 0.141.1, pandas 3.0.5, SQLAlchemy 2.0.52, Uvicorn 0.52.3, React 19.2.8, Vite 8.2.2 and `@vitejs/plugin-react` 6.1.0.

Vite 8 requires Node.js 20.19+ (or a current compatible Node release). If your machine still has Node 20.17, upgrade Node before running the frontend.

## Local setup — Windows beginner path

### 1. Install prerequisites

- Python 3.12
- Node.js 20.19+ or 22+
- Git

### 2. Open PowerShell in this folder

```powershell
cd C:\Users\Lenovo\Downloads\ai-finance-controller-v3
```

### 3. Create and activate Python environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

### 4. Install backend

```powershell
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
```

### 5. Generate demo data

```powershell
python scripts\generate_dataset.py
```

### 6. Start backend

```powershell
python -m uvicorn backend.app.main:app --reload --port 8000
```

Keep this terminal open.

### 7. Start frontend in a second terminal

```powershell
cd frontend
npm install
npm run dev
```

Open:

http://localhost:5173

### 8. Demo sequence

1. Click **Demo data**.
2. Click **Run reconciliation**.
3. Review match rate, precision/recall/F1, throughput and amount at risk.
4. Open an exception.
5. Read the system explanation.
6. Click **AI explain**.
7. Approve/reject the exception.
8. Open **Audit Trail**.
9. Ask Finance Copilot: `What is the amount at risk?`

## AI configuration

Do not hard-code API keys in source code.

Copy:

```powershell
copy .env.example .env
```

Then configure:

```env
AI_API_KEY=your_rotated_key
AI_BASE_URL=https://your-openai-compatible-provider/v1
AI_MODEL=your-model
```

If these are blank, LedgerIQ still works using the deterministic finance reasoner.

**Security:** never commit `.env` to GitHub. If a real key was previously pasted into chat or committed anywhere, revoke/rotate it.

## Production build

```powershell
cd frontend
npm run build
cd ..
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

Then open:

http://localhost:8000

## Docker

```powershell
docker compose up --build
```

Open:

http://localhost:8000

## GitHub

```powershell
git init
git add .
git commit -m "LedgerIQ v3 - AI Finance Controller"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/ledgeriq-ai-finance-controller.git
git push -u origin main
```

Before pushing:

```powershell
git status
```

Make sure `.env`, `.venv`, `node_modules`, the local SQLite database and generated CSVs are not staged.

📥 Using Your Own Custom Data

LedgerIQ supports custom CSV datasets.

The minimum required files are:
orders.csv, 
payment_gateway.csv ,
bank_transactions.csv ,

1. orders.csv
Required columns:

order_id
date
amount
description

Example:

order_id,date,amount,description
ORD-1001,2026-08-20,1499,Mobile order
ORD-1002,2026-08-20,2499,Laptop accessories
ORD-1003,2026-08-21,999,Keyboard order

2. payment_gateway.csv
Required columns:

gateway_id
order_id
date
amount
description

Example:

gateway_id,order_id,date,amount,description
PAY-1001,ORD-1001,2026-08-20,1499,Mobile payment
PAY-1002,ORD-1002,2026-08-20,2499,Laptop payment
PAY-1003,ORD-1003,2026-08-21,999,Keyboard payment

3. bank_transactions.csv
Required columns:

bank_id
gateway_id
date
amount
description

Example:

bank_id,gateway_id,date,amount,description
BANK-1001,PAY-1001,2026-08-21,1499,Settlement
BANK-1002,PAY-1002,2026-08-21,2499,Settlement
BANK-1003,PAY-1003,2026-08-21,999,Settlement

4. Optional ground_truth.csv
Ground truth is required if you want to calculate validation metrics such as:

Precision
Recall
F1

The exact schema should match the version of the metrics service included in the repository.

If ground truth is unavailable:

Precision = N/A
Recall = N/A
F1 = N/A

Do not interpret this as the reconciliation engine having zero accuracy.

📤 Upload Custom CSVs

Start LedgerIQ.

Open:

http://localhost:5173

Click:

Upload CSVs

Select:

orders.csv
payment_gateway.csv
bank_transactions.csv

Then click:

Run reconciliation

LedgerIQ will process the uploaded dataset.

🔎 What to Inspect After Reconciliation

After processing, check:

Dashboard
Records Processed
Matched / Probable
Needs Review
Unresolved
Amount at Risk
Throughput
Quality Metrics

Check:

Match Rate
Precision
Recall
F1
Processing Time
Validation Set

Remember:

Precision/Recall/F1 require ground-truth labels.


🚨 Exception Queue

The exception queue shows records requiring attention.

Typical examples:

Missing Payment
Missing Settlement
Amount Mismatch
Gateway Only
Bank Only
Probable Match Review
Unresolved
💰 Amount at Risk

The amount-at-risk dashboard allows finance users to understand the financial impact of unresolved records.

Example:

₹36,058

This allows the user to prioritize exceptions based on monetary impact.

🤖 Finance Copilot

Example questions:

How many unresolved records are there?

What is the amount at risk?

Which exception is most common?

How many transactions are matched?

How many records need review?

What is the current reconciliation status?

The Copilot is intended to summarize the current reconciliation state rather than act as an unrestricted financial advisor.

🧾 Audit Trail

The audit trail records important workflow events.

Typical events:

Dataset upload
Reconciliation start
Reconciliation completion
Exception review
Exception approval
Exception rejection
AI explanation request

This provides traceability for finance operations.

🧠 Why Deterministic Logic + AI?

LedgerIQ deliberately separates:

Financial decisioning

from

AI explanation

The reconciliation engine is deterministic and evidence-driven.

AI is used where it adds value:

Raw exception
      ↓
Structured evidence
      ↓
Deterministic classification
      ↓
AI explanation
      ↓
Human decision

This avoids making an LLM the sole authority for money-critical reconciliation decisions.

