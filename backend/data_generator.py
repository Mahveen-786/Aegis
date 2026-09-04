"""
data_generator.py - Synthetic Dataset Generator for Merchant Personas

Generates customers, transactions, and disputes for two distinct synthetic
merchants. Nothing here is real merchant/customer data. Ground-truth labels
are seeded explicitly so every downstream module (fraud-spike, return-risk,
abuse-ring, chargeback) has something honest to be evaluated against.
"""
import numpy as np
import pandas as pd
import random
from datetime import datetime, timedelta

PERSONA_CONFIG = {
    "apparel": {
        "name": "Merchant A: D2C Apparel Brand",
        "focus": "High RTO & COD Risk",
        "categories": ["T-Shirts", "Dresses", "Footwear", "Jeans", "Accessories"],
        "cat_weights": [0.35, 0.25, 0.20, 0.15, 0.05],
        "payment_methods": ["COD", "UPI", "Credit Card", "Debit Card"],
        "pm_weights": [0.48, 0.35, 0.10, 0.07],
        "avg_aov": 1350, "aov_std": 600,
        "base_fraud_prob": 0.008,
        "return_rate_alpha_beta": (2, 8),   # customer historical_return_rate ~ Beta(2,8) -> mean ~0.2
    },
    "saas": {
        "name": "Merchant B: Digital SaaS & Electronics",
        "focus": "High Chargeback & Card Fraud",
        "categories": ["Monthly SaaS", "Annual Cloud Sub", "Audio Hardware", "Smart Gadgets", "E-Vouchers"],
        "cat_weights": [0.40, 0.20, 0.20, 0.15, 0.05],
        "payment_methods": ["Credit Card", "UPI", "Netbanking", "Debit Card"],
        "pm_weights": [0.55, 0.25, 0.12, 0.08],
        "avg_aov": 7800, "aov_std": 4200,
        "base_fraud_prob": 0.035,
        "return_rate_alpha_beta": (2, 25),  # mean ~0.07
    },
}

N_CUSTOMERS = 4000
N_TRANSACTIONS = 40000
N_DAYS = 90
DISPUTE_REASONS = ["item_not_received", "unauthorized_transaction", "not_as_described", "duplicate_charge"]


def generate_merchant_data(persona: str = "apparel", seed: int = 42):
    if persona not in PERSONA_CONFIG:
        raise ValueError(f"Unknown persona: {persona}")
    cfg = PERSONA_CONFIG[persona]
    rng = np.random.default_rng(seed)
    random.seed(seed)

    start_date = datetime(2026, 1, 1)

    # ---------------------------------------------------------------
    # Customers, with a seeded subset organized into abuse rings that
    # share device / IP / address. Ring membership is per-CUSTOMER
    # (not per-transaction), so precision/recall is well-defined.
    # ---------------------------------------------------------------
    cust_ids = [f"CUST_{persona[:3].upper()}_{i:05d}" for i in range(N_CUSTOMERS)]

    n_ring_clusters = 18
    ring_size_range = (3, 8)
    ring_device = {}
    ring_ip = {}
    ring_addr = {}
    ring_id_of = {}
    idx = 0
    for r in range(n_ring_clusters):
        size = int(rng.integers(*ring_size_range))
        members = cust_ids[idx: idx + size]
        idx += size
        if not members:
            break
        shared_device = f"DEV_RING_{persona[:3].upper()}_{r:03d}"
        shared_ip = f"10.{rng.integers(1, 255)}.{rng.integers(1, 255)}.{rng.integers(1, 255)}"
        shared_addr = f"Ring Cluster Block {r}, Sector {rng.integers(1, 40)}"
        for m in members:
            ring_device[m] = shared_device
            ring_ip[m] = shared_ip
            ring_addr[m] = shared_addr
            ring_id_of[m] = r

    a, b = cfg["return_rate_alpha_beta"]
    customers = []
    for cid in cust_ids:
        in_ring = cid in ring_device
        customers.append({
            "customer_id": cid,
            "account_age_days": int(rng.exponential(180)) + 1,
            "historical_return_rate": round(float(np.clip(rng.beta(a, b), 0, 0.9)), 3),
            "in_abuse_ring": in_ring,
            "ring_id": ring_id_of.get(cid, -1),
            "home_device": ring_device.get(cid, f"DEV_{persona[:3].upper()}_{rng.integers(10000, 99999)}"),
            "home_ip": ring_ip.get(cid, f"{rng.integers(10,200)}.{rng.integers(0,255)}.{rng.integers(0,255)}.{rng.integers(1,254)}"),
            "home_address": ring_addr.get(cid, f"{rng.integers(1,9999)} {random.choice(['MG Road','Park Street','Church Street','Brigade Road','Ring Road','Station Road'])}, "
                                                f"{random.choice(['Bengaluru','Mumbai','Delhi','Hyderabad','Pune','Chennai','Kolkata','Ahmedabad'])}"),
        })
    df_customers = pd.DataFrame(customers)
    cust_lookup = df_customers.set_index("customer_id").to_dict("index")

    # ---------------------------------------------------------------
    # Transactions, with seeded fraud-spike days
    # ---------------------------------------------------------------
    spike_days = sorted(rng.choice(N_DAYS, size=4, replace=False).tolist())

    txns = []
    for i in range(N_TRANSACTIONS):
        cid = random.choice(cust_ids)
        crec = cust_lookup[cid]
        in_ring = crec["in_abuse_ring"]

        day_offset = int(rng.integers(0, N_DAYS))
        txn_time = start_date + timedelta(days=day_offset, seconds=int(rng.integers(0, 86400)))
        is_spike_day = day_offset in spike_days

        category = str(rng.choice(cfg["categories"], p=cfg["cat_weights"]))
        pm = str(rng.choice(cfg["payment_methods"], p=cfg["pm_weights"]))
        amount = max(299.0, round(float(rng.normal(cfg["avg_aov"], cfg["aov_std"])), 2))
        discount_pct = round(float(rng.beta(2, 5) * 60), 1) if persona == "apparel" else round(float(rng.beta(1, 8) * 30), 1)

        # fraud ground truth
        p_fraud = cfg["base_fraud_prob"]
        if is_spike_day:
            p_fraud *= 7.0
        if in_ring:
            p_fraud += 0.35
        is_fraud = bool(rng.random() < min(p_fraud, 0.9))

        # device/ip used on this transaction: fraud sometimes spoofs away from home identifiers
        if is_fraud and rng.random() < 0.5:
            device_id = f"DEV_SPOOF_{rng.integers(10000,99999)}"
            ip_address = f"{rng.integers(1,255)}.{rng.integers(0,255)}.{rng.integers(0,255)}.{rng.integers(1,254)}"
        else:
            device_id = crec["home_device"]
            ip_address = crec["home_ip"]
        delivery_address = crec["home_address"] if rng.random() < 0.85 else (
            f"{rng.integers(1,9999)} {random.choice(['MG Road','Park Street','Church Street','Brigade Road','Ring Road','Station Road'])}, "
            f"{random.choice(['Bengaluru','Mumbai','Delhi','Hyderabad','Pune','Chennai','Kolkata','Ahmedabad'])}"
        )

        # return ground truth (logit form, RTO-flavored)
        return_logit = (-2.0
                         + (1.2 if pm == "COD" else -0.5)
                         + (discount_pct / 25.0)
                         + (crec["historical_return_rate"] * 2.5)
                         + (-0.8 if crec["account_age_days"] > 90 else 0.6))
        return_prob = 1.0 / (1.0 + np.exp(-return_logit))
        is_returned = bool(rng.random() < return_prob)

        # chargeback ground truth: only for non-COD, more likely if fraud or ring member
        is_chargeback = False
        if pm != "COD":
            p_cb = 0.01 + (0.30 if is_fraud else 0) + (0.04 if in_ring else 0)
            is_chargeback = bool(rng.random() < min(p_cb, 0.85))

        txns.append({
            "transaction_id": f"TXN_{persona[:3].upper()}_{i:06d}",
            "customer_id": cid,
            "timestamp": txn_time.isoformat(),
            "date": txn_time.strftime("%Y-%m-%d"),
            "day_offset": day_offset,
            "category": category,
            "payment_method": pm,
            "amount_inr": amount,
            "discount_pct": discount_pct,
            "ip_address": ip_address,
            "device_id": device_id,
            "delivery_address": delivery_address,
            "account_age_days": crec["account_age_days"],
            "cust_return_rate": crec["historical_return_rate"],
            "in_abuse_ring": in_ring,
            "ring_id": crec["ring_id"],
            "is_returned": is_returned,
            "is_fraud": is_fraud,
            "is_chargeback": is_chargeback,
        })

    df_txns = pd.DataFrame(txns)

    # ---------------------------------------------------------------
    # Disputes: one row per chargeback transaction, with on-file
    # evidence fields and a ground-truth merchant_wins outcome.
    # ---------------------------------------------------------------
    disputes = []
    cb_txns = df_txns[df_txns.is_chargeback]
    for _, t in cb_txns.iterrows():
        reason = random.choice(DISPUTE_REASONS)
        has_3ds = bool(rng.random() < (0.75 if not t.is_fraud else 0.30))
        has_pod = bool(rng.random() < (0.70 if not t.is_fraud else 0.25))
        has_ip_match = bool(rng.random() < (0.80 if not t.is_fraud else 0.25))
        has_policy = bool(rng.random() < 0.85)
        prior_disputes = int(rng.poisson(0.3 if not t.in_abuse_ring else 1.6))

        strength = sum([has_3ds, has_pod, has_ip_match, has_policy])
        p_win = 0.10 + strength * 0.16 - (0.35 if t.is_fraud else 0) - 0.04 * min(prior_disputes, 3)
        merchant_wins = bool(rng.random() < min(max(p_win, 0.02), 0.95))

        disputes.append({
            "dispute_id": f"DISP_{persona[:3].upper()}_{len(disputes):05d}",
            "transaction_id": t.transaction_id,
            "customer_id": t.customer_id,
            "reason_code": reason,
            "amount_inr": t.amount_inr,
            "has_3ds_auth": has_3ds,
            "has_carrier_pod": has_pod,
            "has_ip_match": has_ip_match,
            "has_terms_acceptance": has_policy,
            "prior_dispute_count": prior_disputes,
            "merchant_wins": merchant_wins,
        })
    df_disputes = pd.DataFrame(disputes)

    return {
        "customers": df_customers,
        "transactions": df_txns,
        "disputes": df_disputes,
        "spike_days": spike_days,
        "config": cfg,
    }


if __name__ == "__main__":
    for p in ["apparel", "saas"]:
        d = generate_merchant_data(p)
        txns = d["transactions"]
        print(f"{p}: {len(txns)} txns | fraud={txns.is_fraud.mean():.3f} "
              f"return={txns.is_returned.mean():.3f} chargeback={txns.is_chargeback.mean():.3f} "
              f"| disputes={len(d['disputes'])} | ring_customers={d['customers'].in_abuse_ring.sum()} "
              f"| spike_days={d['spike_days']}")
