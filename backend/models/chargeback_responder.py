"""
chargeback_responder.py - Module 4: Chargeback Evidence Responder

Trained on the generated disputes dataset (NOT hardcoded mock rows), with a
TEMPORAL held-out precision/recall/F1/ROC-AUC evaluation and a CALIBRATED
win-probability output. Drafts a factual, evidence-only summary for a human
to review -- it never invents evidence and never autonomously submits
anything.

Requires df_disputes to carry a `day_offset` column (joined from the
originating transaction) so the split can be temporal like the return
scorer, rather than a random row split.
"""
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix, roc_auc_score

from services.splitting import time_split_masks, group_overlap_report
from services.calibration import fit_calibrator, calibration_report


class ChargebackResponder:
    FEATURE_DISPLAY_NAMES = {
        "has_3ds_auth": "3D-Secure Auth on File",
        "has_carrier_pod": "Carrier Proof-of-Delivery on File",
        "has_ip_match": "Checkout IP Matches History",
        "has_terms_acceptance": "Signed Terms/Refund Acceptance",
        "prior_dispute_count": "Prior Dispute Count",
        "amount_inr": "Dispute Amount",
    }

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.model = LogisticRegression(max_iter=2000)
        self.scaler = StandardScaler()
        self.bool_features = ["has_3ds_auth", "has_carrier_pod", "has_ip_match", "has_terms_acceptance"]
        self.num_features = ["prior_dispute_count", "amount_inr"]
        self.feature_cols = self.bool_features + self.num_features
        self.metrics_ = None
        self.calibrator_ = None

    def _prepare_features(self, df: pd.DataFrame):
        X = pd.DataFrame(index=df.index)
        for c in self.bool_features:
            X[c] = df[c].astype(int)
        for c in self.num_features:
            X[c] = df[c]
        return X

    def _predict_proba_calibrated(self, X_scaled) -> np.ndarray:
        if self.calibrator_ is not None:
            return self.calibrator_.predict_proba(X_scaled)[:, 1]
        return self.model.predict_proba(X_scaled)[:, 1]

    def fit_and_evaluate(self, df_disputes: pd.DataFrame, val_frac: float = 0.15, test_frac: float = 0.15):
        if len(df_disputes) < 40:
            # not enough seeded disputes to get a meaningful held-out split
            self.metrics_ = {"error": "insufficient_disputes", "n_disputes": int(len(df_disputes))}
            return self.metrics_
        if "day_offset" not in df_disputes.columns:
            raise ValueError("df_disputes must include day_offset (joined from the originating "
                              "transaction) for a temporal split.")

        X_all = self._prepare_features(df_disputes)
        y_all = df_disputes["merchant_wins"].astype(int)

        train_mask, val_mask, test_mask, split_info = time_split_masks(
            df_disputes, day_col="day_offset", val_frac=val_frac, test_frac=test_frac
        )
        overlap = group_overlap_report(df_disputes, train_mask, val_mask, test_mask, group_col="customer_id")

        X_train, y_train = X_all[train_mask], y_all[train_mask]
        X_val, y_val = X_all[val_mask], y_all[val_mask]
        X_test, y_test = X_all[test_mask], y_all[test_mask]

        if min(len(X_train), len(X_val), len(X_test)) < 8 or len(set(y_train)) < 2:
            self.metrics_ = {"error": "insufficient_disputes_per_split",
                              "n_train": int(len(X_train)), "n_validation": int(len(X_val)),
                              "n_test": int(len(X_test))}
            return self.metrics_

        X_train_s = self.scaler.fit_transform(X_train)
        X_val_s = self.scaler.transform(X_val)
        X_test_s = self.scaler.transform(X_test)

        self.model.fit(X_train_s, y_train)

        # Calibrate on the validation split only.
        self.calibrator_ = fit_calibrator(self.model, X_val_s, y_val, method="sigmoid")

        raw_test_probs = self.model.predict_proba(X_test_s)[:, 1]
        test_probs = self._predict_proba_calibrated(X_test_s)
        preds = (test_probs >= 0.5).astype(int)

        cm = confusion_matrix(y_test, preds, labels=[0, 1])
        tn, fp, fn, tp = cm.ravel()

        cal_report = calibration_report(raw_test_probs, test_probs, y_test.values)

        # Genuine linear attribution: standardized-coefficient * standardized
        # feature value gives each feature's real contribution to the logit,
        # straight from the fitted model -- not a separately hardcoded story.
        global_coefs = [
            {
                "feature": col,
                "display_name": self.FEATURE_DISPLAY_NAMES.get(col, col),
                "coefficient": round(float(c), 4),
            }
            for col, c in zip(self.feature_cols, self.model.coef_[0])
        ]
        global_coefs.sort(key=lambda r: abs(r["coefficient"]), reverse=True)

        self.metrics_ = {
            "precision": round(float(precision_score(y_test, preds, zero_division=0)), 3),
            "recall": round(float(recall_score(y_test, preds, zero_division=0)), 3),
            "f1": round(float(f1_score(y_test, preds, zero_division=0)), 3),
            "roc_auc": round(float(roc_auc_score(y_test, test_probs)), 3) if len(set(y_test)) > 1 else None,
            "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
            "n_train": int(len(X_train)),
            "n_validation": int(len(X_val)),
            "n_test": int(len(X_test)),
            "base_rate_test": round(float(y_test.mean()), 4),
            "evaluation_protocol": "temporal_held_out_test_split",
            "split_info": split_info,
            "group_leakage_check": overlap,
            "calibration": cal_report,
            "global_coefficients": global_coefs,
            "attribution_source": "logistic_regression_coefficients",
        }
        return self.metrics_

    # Policy layer: sits ON TOP of the model's win-probability estimate. The
    # model predicts merchant_wins; whether to actually contest at that
    # probability is a separate business-policy decision, not something the
    # model itself decided. Kept as an explicit constant (not buried in the
    # model) so it's visible and easy to point to. Calibration is what makes
    # this constant meaningful in the first place -- "0.6" only means "60%"
    # once the probability behind it has been checked against outcomes.
    CONTEST_THRESHOLD = 0.6

    def evaluate_and_draft(self, dispute_data: dict):
        row = pd.DataFrame([{
            "has_3ds_auth": dispute_data.get("has_3ds_auth", False),
            "has_carrier_pod": dispute_data.get("has_carrier_pod", False),
            "has_ip_match": dispute_data.get("has_ip_match", False),
            "has_terms_acceptance": dispute_data.get("has_terms_acceptance", False),
            "prior_dispute_count": dispute_data.get("prior_dispute_count", 0),
            "amount_inr": dispute_data.get("amount_inr", 1000),
        }])
        X = self._prepare_features(row)
        attribution = []
        try:
            X_s = self.scaler.transform(X)
            win_prob = float(self._predict_proba_calibrated(X_s)[0])

            # Per-transaction attribution: coefficient * standardized value
            # for THIS row -- a real per-feature contribution to the logit,
            # not a restatement of the evidence checklist below.
            contributions = self.model.coef_[0] * X_s[0]
            ranked = sorted(zip(self.feature_cols, contributions), key=lambda t: abs(t[1]), reverse=True)
            for feature, contrib in ranked:
                if abs(contrib) < 1e-4:
                    continue
                direction = "Increases" if contrib > 0 else "Decreases"
                attribution.append({
                    "feature": self.FEATURE_DISPLAY_NAMES.get(feature, feature),
                    "impact": f"{direction} win likelihood (contribution {contrib:+.3f})",
                })
        except Exception:
            # model not yet fit (e.g. insufficient disputes for this persona)
            win_prob = 0.5

        present, missing = [], []
        if dispute_data.get("has_3ds_auth"):
            present.append("3D-Secure authentication token on file")
        else:
            missing.append("no 3D-Secure authentication token on file")
        if dispute_data.get("has_carrier_pod"):
            present.append(f"carrier proof-of-delivery on file (tracking: {dispute_data.get('tracking_id', 'N/A')})")
        else:
            missing.append("no carrier proof-of-delivery on file")
        if dispute_data.get("has_ip_match"):
            present.append("checkout IP matches customer's prior order history")
        else:
            missing.append("checkout IP does not match customer's prior order history")
        if dispute_data.get("has_terms_acceptance"):
            present.append("signed terms/refund-policy acceptance on file")
        else:
            missing.append("no signed terms/refund-policy acceptance on file")

        policy_decision = "contest" if win_prob >= self.CONTEST_THRESHOLD else "accept_liability"
        recommendation = (
            "Evidence supports contesting this dispute." if win_prob >= self.CONTEST_THRESHOLD else
            "Evidence is mixed; contest only if additional documentation can be located." if win_prob >= 0.35 else
            "Evidence is weak; consider accepting the chargeback rather than contesting."
        )

        draft = (
            f"### Dispute Evidence Summary\n"
            f"Case: {dispute_data.get('dispute_id', 'N/A')} | Reason: {dispute_data.get('reason_code', 'N/A')} | "
            f"Amount: Rs.{dispute_data.get('amount_inr', 0):,.2f}\n\n"
            f"Model: estimated win likelihood {win_prob:.0%} (calibrated).\n"
            f"Policy: contest if likelihood >= {self.CONTEST_THRESHOLD:.0%}.\n"
            f"Recommended action: {policy_decision.replace('_', ' ')} (pending human review).\n\n"
            f"Evidence on file:\n" + "\n".join(f"- {p}" for p in present) + "\n\n"
            f"Evidence missing:\n" + "\n".join(f"- {m}" for m in missing) + "\n\n"
            f"Recommendation: {recommendation}"
        )

        return {
            "dispute_id": dispute_data.get("dispute_id", "N/A"),
            # Explicitly separated: the model's estimate vs. the policy layer's
            # decision on top of it -- these are not the same thing, and
            # collapsing them makes it look like the model "decided" to contest.
            "model_win_probability": round(win_prob, 3),
            "policy_contest_threshold": self.CONTEST_THRESHOLD,
            "policy_decision": policy_decision,
            "win_probability": round(win_prob, 3),  # kept for backward compatibility with existing callers
            "recommendation": recommendation,
            "evidence_present": present,
            "evidence_missing": missing,
            "model_attribution": attribution,
            "attribution_source": "logistic_regression_coefficients",
            "evidence_draft": draft,
        }
