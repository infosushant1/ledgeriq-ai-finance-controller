# LedgerIQ — AI Finance Controller

A buildathon-ready multi-source reconciliation controller for finance operations.

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

