"""
threshold_sweep.py - Precomputes the Risk Appetite curve for the
return-risk scorer (the module with a live probability output suited to
threshold tuning) with EXPLICIT, stated INR unit-cost assumptions.

These unit costs are illustrative assumptions, not measured from a real
merchant's books -- stated here so a reviewer can see exactly how the
false-positive / false-negative cost figures were derived, and can swap in
real numbers for production use.
"""
import numpy as np
from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix

# Illustrative INR unit costs -- see README for the reasoning behind these.
COST_ASSUMPTIONS_INR = {
    "false_positive_cost": 20,     # unnecessary manual review / friction on a legitimate order
    "false_negative_cost": 350,    # avg net loss (shipping + restock + markdown) on a missed high-risk return
}


def compute_threshold_curve(probs: np.ndarray, y_true: np.ndarray,
                             cost_fp_inr: float = COST_ASSUMPTIONS_INR["false_positive_cost"],
                             cost_fn_inr: float = COST_ASSUMPTIONS_INR["false_negative_cost"]):
    sweep = []
    for t in np.arange(0.10, 0.95, 0.05):
        t_val = round(float(t), 2)
        preds = (probs >= t_val).astype(int)

        prec = float(precision_score(y_true, preds, zero_division=0))
        rec = float(recall_score(y_true, preds, zero_division=0))
        f1 = float(f1_score(y_true, preds, zero_division=0))
        cm = confusion_matrix(y_true, preds, labels=[0, 1])
        tn, fp, fn, tp = cm.ravel()

        cost_fp = fp * cost_fp_inr
        cost_fn = fn * cost_fn_inr

        sweep.append({
            "threshold": t_val,
            "precision": round(prec, 3),
            "recall": round(rec, 3),
            "f1": round(f1, 3),
            "true_positives": int(tp), "true_negatives": int(tn),
            "false_positives": int(fp), "false_negatives": int(fn),
            "cost_fp_inr": round(float(cost_fp), 2),
            "cost_fn_inr": round(float(cost_fn), 2),
            "total_loss_inr": round(float(cost_fp + cost_fn), 2),
        })
    return sweep


def find_optimal_threshold(sweep: list) -> dict | None:
    """The point on the sweep that minimizes total stated cost -- surfaced
    explicitly so the slider can show a recommendation, not just a curve."""
    if not sweep:
        return None
    return min(sweep, key=lambda row: row["total_loss_inr"])
