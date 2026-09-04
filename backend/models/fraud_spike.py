"""
fraud_spike.py - Module 1: Robust Rolling Z-score Spike Detector

Detects days where a merchant's daily fraud rate deviates sharply from its
own trailing baseline (median absolute deviation, robust to outliers).
Evaluated against the seeded ground-truth spike days from the generator so
precision/recall are real numbers, not just asserted.
"""
import pandas as pd
import numpy as np
from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix


class FraudSpikeDetector:
    def __init__(self, window_days: int = 14, threshold_z: float = 3.0):
        self.window_days = window_days
        self.threshold_z = threshold_z
        self.daily_ = None
        self.metrics_ = None

    def fit_and_evaluate(self, df_txns: pd.DataFrame, true_spike_days: list):
        daily = df_txns.groupby("day_offset").agg(
            total_txns=("transaction_id", "count"),
            fraud_txns=("is_fraud", "sum"),
        ).reset_index()

        all_days = pd.DataFrame({"day_offset": range(int(df_txns.day_offset.max()) + 1)})
        daily = all_days.merge(daily, on="day_offset", how="left").fillna(0)
        daily["fraud_rate"] = daily.fraud_txns / daily.total_txns.replace(0, np.nan)
        daily["fraud_rate"] = daily["fraud_rate"].fillna(0)

        # IMPORTANT: baseline uses only PRIOR days (shift(1) before rolling),
        # so a spike day never partially props up the "normal" baseline it's
        # being compared against.
        prior_rate = daily.fraud_rate.shift(1)
        roll_med = prior_rate.rolling(self.window_days, min_periods=5).median()
        mad = (prior_rate - roll_med).abs().rolling(self.window_days, min_periods=5).median()
        robust_z = 0.6745 * (daily.fraud_rate - roll_med) / mad.replace(0, np.nan)
        daily["robust_z"] = robust_z.fillna(0)
        daily["is_spike"] = daily.robust_z > self.threshold_z

        daily["true_spike"] = daily.day_offset.isin(true_spike_days)

        y_true = daily.true_spike.astype(int)
        y_pred = daily.is_spike.astype(int)
        cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
        tn, fp, fn, tp = cm.ravel()

        self.daily_ = daily
        self.metrics_ = {
            "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 3),
            "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 3),
            "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 3),
            "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
            "n_days": int(len(daily)),
            "n_true_spike_days": int(y_true.sum()),
            "n_flagged_days": int(y_pred.sum()),
            "flagged_days": daily[daily.is_spike].day_offset.tolist(),
            "true_spike_days": sorted(true_spike_days),
            # Not a train/test split -- this is a statistical anomaly detector
            # evaluated against seeded ground truth over its full evaluation
            # window, with a strictly backward-looking (prior-days-only) baseline.
            "evaluation_protocol": "full_window_vs_seeded_ground_truth",
            "small_sample_caveat": (
                f"Only {int(y_true.sum())} true spike days in a {len(daily)}-day window -- "
                "precision/recall here have a small denominator and should be read as indicative, "
                "not as a tight estimate."
            ),
        }
        return self.metrics_

    def evaluate_single_date(self, day_offset: int):
        if self.daily_ is None:
            return {"day_offset": day_offset, "z_score": 0.0, "is_spike": False, "fraud_rate": 0.0}
        match = self.daily_[self.daily_.day_offset == day_offset]
        if match.empty:
            return {"day_offset": day_offset, "z_score": 0.0, "is_spike": False, "fraud_rate": 0.0,
                    "recommendation": "Insufficient data"}
        row = match.iloc[0]
        return {
            "day_offset": day_offset,
            "z_score": round(float(row.robust_z), 2),
            "fraud_rate": round(float(row.fraud_rate), 4),
            "is_spike": bool(row.is_spike),
            "recommendation": "Flag day for ops review — fraud rate is a statistical outlier vs. trailing baseline"
            if row.is_spike else "Normal range",
        }
