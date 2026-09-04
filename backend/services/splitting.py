"""
splitting.py - Temporal (day-based) train/validation/test splitting.

Both classifiers in this project (RTO return scorer, chargeback responder)
were previously split with train_test_split(..., stratify=y) -- pure random
row splitting. That has two problems in a deployment where you only ever
have the past to predict the future:

  1. Temporal leakage: the model could train on day 80 and get evaluated on
     day 12. Real deployment never works that way.
  2. Group leakage: a customer with several transactions could land in both
     train and test, letting the model partially memorize that customer's
     behavior (e.g. cust_return_rate) instead of generalizing to new
     customers.

The fix used here is a day-based cut: train on the earliest ~70% of days,
validate on the next ~15%, test on the most recent ~15% (configurable).
This is a GroupShuffleSplit-style guarantee for free -- since every row for
a given transaction lives entirely within one day, no single transaction is
ever duplicated across splits. A customer whose activity happens to straddle
the day boundary will legitimately appear in more than one split (real
customers transact over time), so we compute and report exactly how often
that happens rather than silently assuming it doesn't matter.
"""
import numpy as np
import pandas as pd


def time_split_masks(df: pd.DataFrame, day_col: str = "day_offset",
                      val_frac: float = 0.15, test_frac: float = 0.15):
    """Returns (train_mask, val_mask, test_mask, split_info) as boolean
    Series aligned to df.index, cut purely on day_col so later days are
    never used to predict earlier ones."""
    if not (0 < val_frac < 1 and 0 < test_frac < 1 and val_frac + test_frac < 1):
        raise ValueError("val_frac and test_frac must be in (0,1) and sum to < 1")

    max_day = int(df[day_col].max())
    n_days = max_day + 1
    train_cut_day = int(np.floor(n_days * (1 - val_frac - test_frac)))
    val_cut_day = int(np.floor(n_days * (1 - test_frac)))

    train_mask = df[day_col] < train_cut_day
    val_mask = (df[day_col] >= train_cut_day) & (df[day_col] < val_cut_day)
    test_mask = df[day_col] >= val_cut_day

    split_info = {
        "split_protocol": "temporal_day_based_cut",
        "n_days_total": n_days,
        "train_days": f"0-{train_cut_day - 1}",
        "val_days": f"{train_cut_day}-{val_cut_day - 1}",
        "test_days": f"{val_cut_day}-{max_day}",
    }
    return train_mask, val_mask, test_mask, split_info


def group_overlap_report(df: pd.DataFrame, train_mask, val_mask, test_mask,
                          group_col: str = "customer_id"):
    """Honesty check for the group-leakage concern: reports how many
    customers appear in more than one split as a result of the day cut.
    This is expected (real customers transact across time) and is NOT the
    same failure mode as a single transaction being duplicated across
    splits -- that can't happen here since the split is a strict day cut."""
    train_g = set(df.loc[train_mask, group_col])
    val_g = set(df.loc[val_mask, group_col])
    test_g = set(df.loc[test_mask, group_col])
    all_g = train_g | val_g | test_g
    spanning = (train_g & val_g) | (train_g & test_g) | (val_g & test_g)
    return {
        "n_customers_total": len(all_g),
        "n_customers_spanning_multiple_splits": len(spanning),
        "pct_customers_spanning_multiple_splits": round(len(spanning) / len(all_g), 4) if all_g else 0.0,
        "note": ("A customer spanning splits means they transacted both before and after the "
                 "day cutoff -- expected in a live system. What matters is that no single "
                 "transaction row is duplicated across splits, which the day cut guarantees."),
    }
