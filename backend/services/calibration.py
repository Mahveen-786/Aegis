"""
calibration.py - Post-hoc probability calibration + calibration diagnostics.

Neither classifier previously checked whether predict_proba outputs were
calibrated -- a "0.6" was treated as literally "60% real-world likelihood"
(e.g. CONTEST_THRESHOLD = 0.6 in chargeback_responder.py), but GBDTs
especially are known to be poorly calibrated out of the box, and even
logistic regression can drift under class imbalance.

This module fits a calibrator on the VALIDATION split only (never train,
never the untouched test split), then reports a Brier score and a
reliability diagram (predicted-probability bucket vs. actual outcome rate)
so a reviewer can see whether "0.6" really does mean "60%".
"""
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss

try:
    from sklearn.frozen import FrozenEstimator
    _HAS_FROZEN_ESTIMATOR = True
except ImportError:
    _HAS_FROZEN_ESTIMATOR = False


def fit_calibrator(fitted_estimator, X_val, y_val, method: str = "isotonic"):
    """Wraps an ALREADY-FITTED estimator with a calibrator trained only on
    the validation split. Uses sklearn's FrozenEstimator when available
    (sklearn >= 1.6); falls back to the older cv='prefit' API otherwise."""
    if _HAS_FROZEN_ESTIMATOR:
        calibrator = CalibratedClassifierCV(FrozenEstimator(fitted_estimator), method=method)
    else:  # pragma: no cover - older sklearn fallback
        calibrator = CalibratedClassifierCV(fitted_estimator, method=method, cv="prefit")
    calibrator.fit(X_val, y_val)
    return calibrator


def reliability_diagram(probs, y_true, n_bins: int = 10):
    """Buckets predictions into n_bins equal-width probability buckets and
    compares mean predicted probability to actual observed outcome rate per
    bucket -- a well-calibrated model has these track closely."""
    probs = np.asarray(probs, dtype=float)
    y_true = np.asarray(y_true, dtype=float)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    bucket_idx = np.clip(np.digitize(probs, bins) - 1, 0, n_bins - 1)

    buckets = []
    for b in range(n_bins):
        mask = bucket_idx == b
        n = int(mask.sum())
        if n == 0:
            continue
        buckets.append({
            "bucket_range": [round(float(bins[b]), 2), round(float(bins[b + 1]), 2)],
            "n": n,
            "mean_predicted_prob": round(float(probs[mask].mean()), 4),
            "actual_outcome_rate": round(float(y_true[mask].mean()), 4),
        })
    return buckets


def calibration_report(raw_probs, calibrated_probs, y_true, n_bins: int = 10):
    """Both Brier scores and both reliability diagrams are computed on the
    SAME untouched test split, so this is an apples-to-apples before/after
    comparison of what calibration actually bought."""
    raw_probs = np.asarray(raw_probs, dtype=float)
    calibrated_probs = np.asarray(calibrated_probs, dtype=float)
    y_true = np.asarray(y_true, dtype=float)
    return {
        "brier_score_raw": round(float(brier_score_loss(y_true, raw_probs)), 4),
        "brier_score_calibrated": round(float(brier_score_loss(y_true, calibrated_probs)), 4),
        "reliability_diagram_raw": reliability_diagram(raw_probs, y_true, n_bins),
        "reliability_diagram_calibrated": reliability_diagram(calibrated_probs, y_true, n_bins),
        "calibration_method": "platt_sigmoid_fit_on_validation_split_only",
        "note": ("Lower Brier score is better (0 = perfect, 0.25 = uninformative for a "
                 "balanced problem). Fit exclusively on the validation split and scored here "
                 "on the untouched test split, so this is not the same data the calibrator "
                 "was tuned on. Deployed scores (predict_single / evaluate_and_draft) use the "
                 "calibrated probabilities, not the raw model output."),
    }
