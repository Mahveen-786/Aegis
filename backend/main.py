"""
main.py - Aegis FastAPI Backend

Strictly defense-only: every endpoint here produces a flag, score, or
drafting aid for a human reviewer. Nothing sends messages, submits
disputes, blocks accounts, or takes any action autonomously.
"""
import io
import pandas as pd
from fastapi import FastAPI, UploadFile, File, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from data_generator import generate_merchant_data, PERSONA_CONFIG
from models.fraud_spike import FraudSpikeDetector
from models.return_scorer import RTOReturnScorer
from models.abuse_sentinel import AbuseRingSentinel
from models.chargeback_responder import ChargebackResponder
from audit_store import AuditStore
from services.threshold_sweep import compute_threshold_curve, find_optimal_threshold, COST_ASSUMPTIONS_INR
from services.chat_copilot import explain_risk
from services import model_lineage as lineage_svc

SEED = 42

app = FastAPI(
    title="Aegis API",
    version="1.0.0",
    description="Aegis -- a strictly defense-only risk & loss-prevention platform. "
                 "Detection, scoring, drafting and explanation only -- no offensive capability.",
)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

STATE = {
    "active_persona": "apparel",
    "data": {},       # persona -> {customers, transactions, disputes, spike_days}
    "models": {},      # persona -> {fraud_spike, return_risk, abuse, chargeback}
    "metrics": {},     # persona -> {module: metrics}
    "sweep": {},       # persona -> [threshold curve]
    "lineage": {},     # persona -> {module: lineage record}
    "audit_store": AuditStore(),
}


def _persist_and_log_lineage(persona: str, module_name: str, model_obj, training_df: pd.DataFrame, metrics: dict):
    """Persists a fitted model to disk with joblib and writes a lineage
    record (which data hash + sklearn version + seed produced it) into the
    audit store, so /dashboard/metrics can point at a specific artifact on
    disk instead of implicitly "whatever's currently in memory"."""
    data_hash = lineage_svc.hash_dataframe(training_df)
    model_version = lineage_svc.make_model_version(data_hash, SEED)
    record = lineage_svc.save_model(model_obj, persona, module_name, model_version, data_hash, SEED, metrics)
    STATE["audit_store"].log_model_lineage(
        persona=persona, module_name=module_name, model_version=model_version,
        artifact_path=record["artifact_path"], training_data_hash=data_hash,
        sklearn_version=record["sklearn_version"], seed=SEED,
        trained_at=record["trained_at"], metrics=metrics,
    )
    return {
        "model_version": model_version,
        "artifact_path": record["artifact_path"],
        "training_data_hash": data_hash,
        "sklearn_version": record["sklearn_version"],
        "seed": SEED,
        "trained_at": record["trained_at"],
    }


def _initialize_persona(persona: str):
    gen = generate_merchant_data(persona, seed=SEED)
    customers, txns, disputes = gen["customers"], gen["transactions"], gen["disputes"]

    # Disputes don't carry day_offset natively -- join it from the
    # originating transaction so the chargeback responder can use the same
    # temporal (day-based) split as the return scorer, rather than a random
    # row split.
    disputes = disputes.merge(txns[["transaction_id", "day_offset"]], on="transaction_id", how="left")

    fraud_spike = FraudSpikeDetector()
    fraud_metrics = fraud_spike.fit_and_evaluate(txns, gen["spike_days"])

    return_scorer = RTOReturnScorer(seed=SEED)
    return_metrics, probs, y_test = return_scorer.fit_and_evaluate(txns)

    abuse = AbuseRingSentinel(seed=SEED)
    abuse_metrics = abuse.fit_and_evaluate(txns, customers)

    chargeback = ChargebackResponder(seed=SEED)
    chargeback_metrics = chargeback.fit_and_evaluate(disputes)

    sweep = compute_threshold_curve(probs, y_test)

    lineage = {
        "return_risk_scorer": _persist_and_log_lineage(persona, "return_risk_scorer", return_scorer, txns, return_metrics),
        "chargeback_evidence_responder": _persist_and_log_lineage(persona, "chargeback_evidence_responder", chargeback, disputes, chargeback_metrics),
        "abuse_ring_sentinel": _persist_and_log_lineage(persona, "abuse_ring_sentinel", abuse, txns, abuse_metrics),
        "fraud_spike_detector": _persist_and_log_lineage(persona, "fraud_spike_detector", fraud_spike, txns, fraud_metrics),
    }

    STATE["data"][persona] = {"customers": customers, "transactions": txns,
                               "disputes": disputes, "spike_days": gen["spike_days"]}
    STATE["models"][persona] = {"fraud_spike": fraud_spike, "return_risk": return_scorer,
                                 "abuse": abuse, "chargeback": chargeback}
    STATE["metrics"][persona] = {
        "fraud_spike_detector": fraud_metrics,
        "return_risk_scorer": return_metrics,
        "abuse_ring_sentinel": abuse_metrics,
        "chargeback_evidence_responder": chargeback_metrics,
    }
    STATE["sweep"][persona] = sweep
    STATE["lineage"][persona] = lineage


@app.on_event("startup")
def startup_event():
    for p in PERSONA_CONFIG:
        _initialize_persona(p)


def _persona() -> str:
    return STATE["active_persona"]


# ---------------------------------------------------------------------------
# Personas
# ---------------------------------------------------------------------------
@app.get("/personas")
def get_personas():
    return {
        "active": STATE["active_persona"],
        "available": {k: {"name": v["name"], "focus": v["focus"]} for k, v in PERSONA_CONFIG.items()},
    }


@app.post("/personas/switch")
def switch_persona(persona: str = Query(..., pattern="^(apparel|saas)$")):
    STATE["active_persona"] = persona
    return {"status": "ok", "active_persona": persona}


# ---------------------------------------------------------------------------
# Dashboard: metrics for ALL FOUR modules, and the cost-aware threshold sweep
# ---------------------------------------------------------------------------
@app.get("/dashboard/metrics")
def get_metrics():
    p = _persona()
    return {"persona": p, "modules": STATE["metrics"][p], "lineage": STATE["lineage"].get(p, {})}


@app.get("/dashboard/lineage")
def get_lineage(module: str = None):
    """What produced the numbers currently shown on the dashboard: which
    persisted artifact, trained on which data (by content hash), with which
    library version and seed, and when -- proof that the metrics come from a
    reproducible artifact on disk, not just whatever's in memory right now."""
    p = _persona()
    if module:
        record = STATE["audit_store"].get_latest_lineage(p, module)
        return {"persona": p, "module": module, "lineage": record}
    return {"persona": p, "lineage": STATE["lineage"].get(p, {})}


@app.get("/dashboard/threshold-sweep")
def get_threshold_sweep():
    p = _persona()
    curve = STATE["sweep"][p]
    return {
        "persona": p,
        "module": "return_risk_scorer",
        "cost_assumptions_inr": COST_ASSUMPTIONS_INR,
        "curve": curve,
        "optimal": find_optimal_threshold(curve),
    }


# ---------------------------------------------------------------------------
# Abuse-ring graph
# ---------------------------------------------------------------------------
@app.get("/graph/abuse-rings")
def get_abuse_rings():
    p = _persona()
    sentinel = STATE["models"][p]["abuse"]
    return {
        "clusters": sentinel.clusters[:6],
        "cytoscape_elements": sentinel.get_cytoscape_elements(max_clusters=4),
        "metrics": STATE["metrics"][p]["abuse_ring_sentinel"],
    }


# ---------------------------------------------------------------------------
# Single transaction scoring (fraud-spike day check + return-risk + abuse-ring)
# ---------------------------------------------------------------------------
class SingleTxnInput(BaseModel):
    transaction_id: str = "TXN_LIVE_001"
    customer_id: str = "CUST_APP_00099"
    amount_inr: float = 1899.0
    category: str = "Dresses"
    payment_method: str = "COD"
    discount_pct: float = 35.0
    account_age_days: int = 5
    cust_return_rate: float = 0.45
    day_offset: int = 30


@app.post("/analyze/transaction")
def analyze_transaction(txn: SingleTxnInput, threshold: float = Query(None, ge=0.0, le=1.0)):
    p = _persona()
    txn_dict = txn.dict()
    models = STATE["models"][p]

    return_res = models["return_risk"].predict_single(txn_dict, threshold=threshold)
    STATE["audit_store"].log_event(
        persona=p, target_id=txn.transaction_id, target_type="transaction",
        module_name="return_risk_scorer", score=return_res["score"],
        threshold=return_res["threshold_used"], flagged=return_res["is_flagged"],
        evidence={"factors": return_res["contributing_factors"], "amount_inr": txn.amount_inr,
                  "payment_method": txn.payment_method},
        action=return_res["recommended_action"],
    )

    abuse_res = models["abuse"].inspect_customer(txn.customer_id)
    STATE["audit_store"].log_event(
        persona=p, target_id=txn.customer_id, target_type="customer",
        module_name="abuse_ring_sentinel", score=None, threshold=None,
        flagged=abuse_res["in_ring"],
        evidence={"shared_entities": abuse_res["shared_entities"], "cluster_size": abuse_res["cluster_size"],
                  "evidence_breakdown": abuse_res["evidence_breakdown"]},
        action=abuse_res["recommended_action"],
    )

    spike_res = models["fraud_spike"].evaluate_single_date(txn.day_offset)
    STATE["audit_store"].log_event(
        persona=p, target_id=f"day_{txn.day_offset}", target_type="day",
        module_name="fraud_spike_detector", score=spike_res.get("z_score"),
        threshold=STATE["models"][p]["fraud_spike"].threshold_z, flagged=spike_res["is_spike"],
        evidence={"fraud_rate": spike_res.get("fraud_rate")},
        action=spike_res.get("recommendation", "n/a"),
    )

    return {
        "transaction_id": txn.transaction_id, "persona": p,
        "return_risk": return_res, "abuse_ring": abuse_res, "fraud_spike_day_check": spike_res,
    }


# ---------------------------------------------------------------------------
# Batch CSV upload -- scores every row through the return-risk model
# ---------------------------------------------------------------------------
@app.post("/analyze/batch")
async def analyze_batch(file: UploadFile = File(...), threshold: float = Query(None, ge=0.0, le=1.0)):
    p = _persona()
    content = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {e}")

    required = {"transaction_id", "customer_id", "amount_inr", "category", "payment_method",
                "discount_pct", "account_age_days", "cust_return_rate"}
    missing_cols = required - set(df.columns)
    if missing_cols:
        raise HTTPException(status_code=400, detail=f"CSV missing required columns: {sorted(missing_cols)}")

    return_scorer = STATE["models"][p]["return_risk"]
    abuse = STATE["models"][p]["abuse"]
    results = []
    for _, row in df.iterrows():
        txn_dict = row.to_dict()
        r = return_scorer.predict_single(txn_dict, threshold=threshold)
        a = abuse.inspect_customer(str(row["customer_id"]))
        STATE["audit_store"].log_event(
            persona=p, target_id=str(row["transaction_id"]), target_type="transaction",
            module_name="return_risk_scorer", score=r["score"], threshold=r["threshold_used"],
            flagged=r["is_flagged"], evidence={"factors": r["contributing_factors"]},
            action=r["recommended_action"],
        )
        results.append({"transaction_id": row["transaction_id"], "return_risk": r, "abuse_ring": a})

    return {"persona": p, "n_rows": len(results), "results": results}


# ---------------------------------------------------------------------------
# One-click demo dataset summary (avoids re-uploading the ~40k-row set)
# ---------------------------------------------------------------------------
@app.get("/analyze/demo-dataset")
def load_demo_dataset(limit: int = 25):
    p = _persona()
    txns = STATE["data"][p]["transactions"]
    sample = txns.sample(min(limit, len(txns)), random_state=1)
    return {
        "persona": p,
        "n_total_transactions": len(txns),
        "sample_size": len(sample),
        "sample": sample.to_dict(orient="records"),
    }


# ---------------------------------------------------------------------------
# Chargeback evidence responder
# ---------------------------------------------------------------------------
class DisputeInput(BaseModel):
    dispute_id: str = "DISP_LIVE_001"
    reason_code: str = "unauthorized_transaction"
    amount_inr: float = 4500.0
    has_3ds_auth: bool = False
    has_carrier_pod: bool = True
    has_ip_match: bool = False
    has_terms_acceptance: bool = True
    prior_dispute_count: int = 0
    tracking_id: str = ""


@app.post("/analyze/dispute")
def analyze_dispute(dispute: DisputeInput):
    p = _persona()
    result = STATE["models"][p]["chargeback"].evaluate_and_draft(dispute.dict())
    STATE["audit_store"].log_event(
        persona=p, target_id=dispute.dispute_id, target_type="dispute",
        module_name="chargeback_evidence_responder", score=result["model_win_probability"],
        threshold=result["policy_contest_threshold"], flagged=(result["policy_decision"] == "contest"),
        evidence={"present": result["evidence_present"], "missing": result["evidence_missing"],
                  "policy_decision": result["policy_decision"]},
        action=result["recommendation"],
    )
    return result


# ---------------------------------------------------------------------------
# Audit trail -- first-class, covers all four modules
# ---------------------------------------------------------------------------
@app.get("/audit/log")
def get_audit_log(module: str = None, flagged_only: bool = False, limit: int = 100):
    p = _persona()
    return {
        "persona": p,
        "module_counts": STATE["audit_store"].module_counts(persona=p),
        "logs": STATE["audit_store"].get_logs(persona=p, module=module, flagged_only=flagged_only, limit=limit),
    }


# ---------------------------------------------------------------------------
# Chat copilot
# ---------------------------------------------------------------------------
class ChatQuery(BaseModel):
    query: str
    context_result: dict = None


@app.post("/chat")
def chat_copilot(req: ChatQuery):
    return explain_risk(req.query, req.context_result)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
