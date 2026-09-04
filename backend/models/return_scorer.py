"""
return_scorer.py - Module 2: RTO Return-Risk Scorer (GBDT Classifier)

Scores probability of a Return-to-Origin at checkout time, trained and
evaluated on a TEMPORAL held-out split (train on earliest days, evaluate on
the most recent days -- never the reverse), with a CALIBRATED probability
output and a genuine per-transaction feature attribution (SHAP), not a
hardcoded set of if/else rules.
"""
import numpy as np
import pandas as pd
import shap
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix, roc_auc_score

from services.splitting import time_split_masks, group_overlap_report
from services.calibration import fit_calibrator, calibration_report


class RTOReturnScorer:
    FEATURE_DISPLAY_NAMES = {
        "amount_inr": "Order Amount",
        "discount_pct": "Discount %",
        "account_age_days": "Account Age",
        "cust_return_rate": "Customer Return History",
        "is_cod": "Payment Method (COD)",
        "is_upi": "Payment Method (UPI)",
        "is_apparel_cat": "Apparel Category",
    }

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.model = GradientBoostingClassifier(n_estimators=120, max_depth=3, learning_rate=0.1, random_state=seed)
        self.feature_cols = [
            "amount_inr", "discount_pct", "account_age_days",
            "cust_return_rate", "is_cod", "is_upi", "is_apparel_cat",
        ]
        self.apparel_categories = {"T-Shirts", "Dresses", "Footwear", "Jeans"}
        self.threshold_ = 0.5
        self.metrics_ = None
        self.probs_test_ = None          # calibrated test-split probabilities
        self.y_test_ = None
        self.calibrator_ = None
        self.explainer_ = None           # shap.TreeExplainer, built after fit
        self.feature_importance_ = None

    def _prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        X = pd.DataFrame(index=df.index)
        X["amount_inr"] = df["amount_inr"]
        X["discount_pct"] = df["discount_pct"]
        X["account_age_days"] = df["account_age_days"]
        X["cust_return_rate"] = df["cust_return_rate"]
        X["is_cod"] = (df["payment_method"] == "COD").astype(int)
        X["is_upi"] = (df["payment_method"] == "UPI").astype(int)
        X["is_apparel_cat"] = df["category"].isin(self.apparel_categories).astype(int)
        return X[self.feature_cols]

    def _predict_proba_calibrated(self, X: pd.DataFrame) -> np.ndarray:
        """Every consumer of a probability (threshold, dashboard, live
        scoring) goes through the calibrator, never the raw GBDT output --
        that's the whole point of calibrating in the first place."""
        if self.calibrator_ is not None:
            return self.calibrator_.predict_proba(X)[:, 1]
        return self.model.predict_proba(X)[:, 1]

    def fit_and_evaluate(self, df_txns: pd.DataFrame, val_frac: float = 0.15, test_frac: float = 0.15):
        """Train -> validation -> test, split by DAY (temporal), not by
        random row, so the model only ever trains on the past relative to
        what it's evaluated on. The validation split is used to (a) fit the
        probability calibrator and (b) pick the operating threshold; the
        test split is touched exactly once, after both are locked in."""
        X_all = self._prepare_features(df_txns)
        y_all = df_txns["is_returned"].astype(int)

        train_mask, val_mask, test_mask, split_info = time_split_masks(
            df_txns, day_col="day_offset", val_frac=val_frac, test_frac=test_frac
        )
        overlap = group_overlap_report(df_txns, train_mask, val_mask, test_mask, group_col="customer_id")

        X_train, y_train = X_all[train_mask], y_all[train_mask]
        X_val, y_val = X_all[val_mask], y_all[val_mask]
        X_test, y_test = X_all[test_mask], y_all[test_mask]

        self.model.fit(X_train, y_train)

        # Calibrate on the validation split only (never train, never test).
        self.calibrator_ = fit_calibrator(self.model, X_val, y_val, method="sigmoid")
        val_probs = self._predict_proba_calibrated(X_val)

        # Pick the operating threshold against the CALIBRATED validation
        # probabilities, since that's what every downstream consumer uses.
        best_thr, best_val_f1 = 0.5, -1.0
        for thr in np.arange(0.1, 0.9, 0.02):
            preds = (val_probs >= thr).astype(int)
            f1 = f1_score(y_val, preds, zero_division=0)
            if f1 > best_val_f1:
                best_val_f1, best_thr = f1, thr
        self.threshold_ = float(best_thr)

        # Evaluate ONCE on the untouched test split, at the locked threshold.
        raw_test_probs = self.model.predict_proba(X_test)[:, 1]
        test_probs = self._predict_proba_calibrated(X_test)
        preds = (test_probs >= self.threshold_).astype(int)
        cm = confusion_matrix(y_test, preds, labels=[0, 1])
        tn, fp, fn, tp = cm.ravel()

        cal_report = calibration_report(raw_test_probs, test_probs, y_test.values)

        # Global feature importance (GBDT-native) + permutation importance
        # on the untouched test split, to confirm the GBDT importances
        # reflect real signal and not just noise the model happened to fit.
        perm = permutation_importance(self.model, X_test, y_test, n_repeats=10,
                                       random_state=self.seed, scoring="roc_auc")
        self.feature_importance_ = [
            {
                "feature": col,
                "display_name": self.FEATURE_DISPLAY_NAMES.get(col, col),
                "gbdt_importance": round(float(imp), 4),
                "permutation_importance_mean": round(float(perm.importances_mean[i]), 4),
                "permutation_importance_std": round(float(perm.importances_std[i]), 4),
            }
            for i, (col, imp) in enumerate(zip(self.feature_cols, self.model.feature_importances_))
        ]
        self.feature_importance_.sort(key=lambda r: r["gbdt_importance"], reverse=True)

        # SHAP TreeExplainer for genuine per-transaction attribution later
        # (predict_single). Built once here, reused on every call.
        self.explainer_ = shap.TreeExplainer(self.model)

        self.metrics_ = {
            "precision": round(float(precision_score(y_test, preds, zero_division=0)), 3),
            "recall": round(float(recall_score(y_test, preds, zero_division=0)), 3),
            "f1": round(float(f1_score(y_test, preds, zero_division=0)), 3),
            "roc_auc": round(float(roc_auc_score(y_test, test_probs)), 3),
            "operating_threshold": round(self.threshold_, 2),
            "threshold_selected_on": "validation_split_calibrated_probs",
            "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
            "n_train": int(len(X_train)),
            "n_validation": int(len(X_val)),
            "n_test": int(len(X_test)),
            "base_rate_test": round(float(y_test.mean()), 4),
            "evaluation_protocol": "temporal_held_out_test_split",
            "split_info": split_info,
            "group_leakage_check": overlap,
            "calibration": cal_report,
            "feature_importance": self.feature_importance_,
            "attribution_source": "shap_tree_explainer",
        }
        self.probs_test_ = test_probs
        self.y_test_ = y_test.values
        return self.metrics_, test_probs, y_test.values

    def _format_feature_value(self, feature: str, txn_dict: dict) -> str:
        if feature == "amount_inr":
            return f"Rs.{txn_dict.get('amount_inr', 0):,.0f}"
        if feature == "discount_pct":
            return f"{txn_dict.get('discount_pct', 0)}%"
        if feature == "account_age_days":
            return f"{txn_dict.get('account_age_days', 0)} days old"
        if feature == "cust_return_rate":
            return f"{txn_dict.get('cust_return_rate', 0):.0%} historical return rate"
        if feature == "is_cod":
            return "COD" if txn_dict.get("payment_method") == "COD" else "Not COD"
        if feature == "is_upi":
            return "UPI" if txn_dict.get("payment_method") == "UPI" else "Not UPI"
        if feature == "is_apparel_cat":
            cat = txn_dict.get("category", "")
            return f"{cat} ({'apparel' if cat in self.apparel_categories else 'non-apparel'})"
        return str(txn_dict.get(feature, ""))

    def predict_single(self, txn_dict: dict, threshold: float | None = None, top_k: int = 4):
        thr = threshold if threshold is not None else self.threshold_
        df = pd.DataFrame([txn_dict])
        X = self._prepare_features(df)
        prob = float(self._predict_proba_calibrated(X)[0])
        is_flagged = prob >= thr

        # Genuine per-transaction attribution via SHAP, not hardcoded rules
        # -- these numbers come directly from the trained model's own
        # response to THIS row, so if the model learned something
        # surprising, the factors shown reflect that surprise instead of
        # silently overriding it with a fixed if/else list.
        factors = []
        if self.explainer_ is not None:
            shap_values = self.explainer_.shap_values(X)
            row_shap = np.asarray(shap_values)[0]
            ranked = sorted(zip(self.feature_cols, row_shap), key=lambda t: abs(t[1]), reverse=True)
            for feature, val in ranked[:top_k]:
                if abs(val) < 1e-4:
                    continue
                direction = "Increases" if val > 0 else "Decreases"
                factors.append({
                    "feature": self.FEATURE_DISPLAY_NAMES.get(feature, feature),
                    "value": self._format_feature_value(feature, txn_dict),
                    "impact": f"{direction} return risk (SHAP {val:+.3f})",
                })
        if not factors:
            factors.append({"feature": "Baseline", "value": "No elevated risk factors detected", "impact": "Within normal range"})

        return {
            "score": round(prob, 3),
            "is_flagged": is_flagged,
            "threshold_used": round(thr, 3),
            "risk_level": "High" if prob > 0.65 else ("Medium" if prob > 0.40 else "Low"),
            "contributing_factors": factors,
            "attribution_source": "shap_tree_explainer" if self.explainer_ is not None else "unavailable",
            "recommended_action": ("Trigger OTP / pre-dispatch address confirmation for human review"
                                    if is_flagged else "No extra verification needed"),
        }
