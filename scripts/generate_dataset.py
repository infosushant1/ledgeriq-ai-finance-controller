from pathlib import Path
from datetime import date, timedelta
import random
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "generated"
OUT.mkdir(parents=True, exist_ok=True)

random.seed(42)

N = 200
start = date(2026, 7, 1)

orders = []
gateways = []
banks = []
truth = []

for i in range(1, N + 1):
    oid = f"ORD-{i:04d}"
    gid = f"PAY-{i:04d}"
    bid = f"BANK-{i:04d}"
    d = start + timedelta(days=i % 31)
    amount = round(random.choice([499, 799, 999, 1499, 1999, 2499, 3499, 4999]) + random.choice([0, 0, 0, 49, 99]), 2)
    desc = f"Merchant order {oid}"
    orders.append({"order_id": oid, "date": d.isoformat(), "amount": amount, "description": desc})

    scenario = "matched"
    if i % 37 == 0:
        scenario = "missing_gateway"
    elif i % 31 == 0:
        scenario = "missing_bank"
    elif i % 29 == 0:
        scenario = "amount_mismatch"
    elif i % 23 == 0:
        scenario = "probable"

    if scenario != "missing_gateway":
        gate_order = oid
        gate_desc = desc
        if scenario == "probable":
            gate_order = ""  # forces soft matching
            gate_desc = f"merchant payment {oid}"
        gateways.append({
            "gateway_id": gid,
            "order_id": gate_order,
            "date": d.isoformat(),
            "amount": amount,
            "description": gate_desc,
        })

    if scenario not in {"missing_gateway", "missing_bank"}:
        bank_amount = amount + (75 if scenario == "amount_mismatch" else 0)
        banks.append({
            "bank_id": bid,
            "gateway_id": gid,
            "date": (d + timedelta(days=1 if scenario == "probable" else 0)).isoformat(),
            "amount": bank_amount,
            "description": f"settlement {gid}",
        })

    expected = "MATCHED" if scenario in {"matched", "probable"} else "UNMATCHED"
    truth.append({"order_id": oid, "expected_status": expected})

# Explicit orphan records make the exception queue business-realistic.
for j in range(1, 11):
    gateways.append({
        "gateway_id": f"PAY-ORPHAN-{j:03d}",
        "order_id": "",
        "date": (start + timedelta(days=j)).isoformat(),
        "amount": 1299 + j * 50,
        "description": "Unattributed gateway payment",
    })

for j in range(1, 9):
    banks.append({
        "bank_id": f"BANK-ORPHAN-{j:03d}",
        "gateway_id": "",
        "date": (start + timedelta(days=j + 2)).isoformat(),
        "amount": 2199 + j * 75,
        "description": "Unattributed bank settlement",
    })

pd.DataFrame(orders).to_csv(OUT / "orders.csv", index=False)
pd.DataFrame(gateways).to_csv(OUT / "payment_gateway.csv", index=False)
pd.DataFrame(banks).to_csv(OUT / "bank_transactions.csv", index=False)
pd.DataFrame(truth).to_csv(OUT / "ground_truth.csv", index=False)

print(f"Generated {len(orders)} orders, {len(gateways)} gateway rows and {len(banks)} bank rows.")
