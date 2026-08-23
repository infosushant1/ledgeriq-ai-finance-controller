from collections import Counter

MATCHED = {"MATCHED", "PROBABLE_MATCH"}

def _pct(a, b):
    return round((a / b) * 100, 2) if b else 0.0

def _binary_metrics(predictions):
    # Ground truth values use MATCHED / UNMATCHED. We evaluate only the labeled validation subset.
    tp = sum(1 for p, y in predictions if p == "MATCHED" and y == "MATCHED")
    fp = sum(1 for p, y in predictions if p == "MATCHED" and y != "MATCHED")
    fn = sum(1 for p, y in predictions if p != "MATCHED" and y == "MATCHED")
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    return {
        "precision": round(precision * 100, 2),
        "recall": round(recall * 100, 2),
        "f1_score": round(f1 * 100, 2),
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "validation_records": len(predictions),
    }

def build_metrics(rows, truth):
    total = len(rows)
    matched = sum(r["status"] in MATCHED for r in rows)
    review = sum(r["status"] == "NEEDS_REVIEW" for r in rows)
    unresolved = sum(r["status"] == "UNRESOLVED" for r in rows)
    exceptions = sum(bool(r.get("exception_type")) for r in rows)
    amount_at_risk = round(sum(float(r.get("amount_at_risk") or 0) for r in rows if r["status"] not in MATCHED), 2)

    breakdown = Counter(
        r.get("exception_type") or "NONE"
        for r in rows
        if r.get("exception_type")
    )

    validation_pairs = []
    truth_map = {str(x["order_id"]): str(x["expected_status"]) for x in truth}
    for r in rows:
        oid = str(r.get("order_id", ""))
        if oid in truth_map:
            predicted = "MATCHED" if r["status"] == "MATCHED" else "UNMATCHED"
            expected = "MATCHED" if truth_map[oid] == "MATCHED" else "UNMATCHED"
            validation_pairs.append((predicted, expected))

    eval_metrics = _binary_metrics(validation_pairs)
    return {
        "total_records": total,
        "matched_or_probable": matched,
        "needs_review": review,
        "unresolved": unresolved,
        "exception_count": exceptions,
        "match_rate": round((matched / total) * 100, 2) if total else 0.0,
        "amount_at_risk": amount_at_risk,
        "exception_breakdown": [
            {"type": k, "count": v}
            for k, v in sorted(breakdown.items(), key=lambda x: (-x[1], x[0]))
        ],
        **eval_metrics,
    }
