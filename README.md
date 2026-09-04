# Aegis — Merchant Risk & Loss Prevention

Aegis is a defense-only merchant risk platform that combines **transaction risk scoring, fraud-spike detection, coordinated abuse detection, and chargeback evidence assistance** into one explainable dashboard.

It is designed as a **decision-support system**: every module produces a score, flag, or evidence draft for human review. Aegis does not automatically block accounts, submit disputes, or take financial actions.


## 🚀 What Aegis Does

### 1. Fraud-Spike Detector
Detects abnormal changes in daily fraud rates using a **backward-looking rolling z-score**.

- No future data is used in the baseline
- Evaluated against seeded spike ground truth
- Designed to surface sudden changes in merchant risk

### 2. Return-Risk Scorer
Predicts the probability that a transaction will result in a high-risk return/RTO.

- Gradient-boosted classifier
- Temporal train → validation → test split
- Platt/sigmoid probability calibration
- SHAP-based per-transaction explanations
- Cost-aware threshold optimization

### 3. Abuse-Ring Sentinel
Detects coordinated customer abuse using a weighted identity graph.

- Shared device, IP, and address relationships
- Device > IP > address edge weighting
- Louvain community detection
- Personalized PageRank risk scores
- Interactive Cytoscape.js network visualization

### 4. Chargeback Evidence Responder
Estimates chargeback win likelihood and produces a fact-based evidence draft.

- Logistic regression
- Temporal evaluation
- Calibrated probabilities
- Feature attribution from model coefficients
- Separates model prediction from business policy

---

## 🧠 Technical Highlights

### Temporal Validation

The supervised models do **not** use random row splitting.

Data is divided chronologically:

```text
Earlier days       Next period          Most recent period
     ↓                  ↓                       ↓
   TRAIN          VALIDATION / CALIBRATION      TEST
                         ↓
                Threshold selection
````

This prevents the model from learning from future transactions when predicting past transactions.

### Probability Calibration

Classifier outputs are calibrated using the validation split.

Aegis reports **Brier scores and reliability information**, so displayed probabilities are treated as probabilities rather than raw model scores.

### Explainability

Return-risk predictions use **SHAP TreeExplainer** for transaction-level attribution.

The chargeback model uses its fitted logistic-regression coefficients and standardized feature values.

Explanations are therefore derived from the trained models rather than manually hardcoded.

### Cost-Aware Risk Appetite

For return-risk decisions, Aegis evaluates different operating thresholds using illustrative business costs:

* False positive: ₹20
* False negative: ₹350

The dashboard allows the merchant to explore the **precision / recall / cost trade-off** and identify the lowest-cost operating threshold.

> These costs are demonstration assumptions and should be replaced with real merchant economics in production.

---

## 📊 Evaluation

Each module is evaluated according to the type of system it actually is:

| Module               | Evaluation                                          |
| -------------------- | --------------------------------------------------- |
| Return-Risk Scorer   | Temporal held-out test split                        |
| Chargeback Responder | Temporal held-out test split                        |
| Fraud-Spike Detector | Full evaluation window vs seeded spike ground truth |
| Abuse-Ring Sentinel  | Full customer graph vs seeded ring ground truth     |

The project uses **synthetic data generated from controlled formulas**, so the metrics demonstrate the behavior of the implemented system rather than claiming production performance on real merchant data.

The dashboard exposes:

* Precision
* Recall
* F1
* AUC where applicable
* Confusion matrices
* Calibration / Brier scores
* Threshold-cost curves

---

## 🏪 Merchant Personas

Aegis includes two distinct synthetic merchant personas with different fraud, return, and chargeback distributions.

This allows the same risk-management architecture to be evaluated under different merchant risk environments rather than simply filtering the same dataset.

---

## 🔍 Auditability & Model Lineage

Aegis is designed with traceability in mind.

### Audit Trail

Every scoring event is recorded with information about:

* Module
* Result
* Evidence
* Timestamp
* Merchant persona

### Model Lineage

Trained models are persisted with `joblib` and linked to lineage information including:

* Training-data hash
* Scikit-learn version
* Random seed
* Timestamp
* Metrics snapshot

This makes dashboard results traceable to a specific model artifact.

---

## 🤖 AI Copilot

Aegis includes a domain-scoped copilot with three paths:

1. **Result-grounded explanation**
   Explains a selected transaction, dispute, or abuse cluster using its structured result.

2. **Glossary lookup**
   Provides definitions for domain terms such as RTO, chargeback, and 3DS.

3. **Out-of-scope refusal**
   Refuses questions outside the system's intended risk-management scope.

The copilot can use an external LLM provider when configured, with a deterministic fallback for demo reliability.

---

## 🛠️ Project Structure

```text
aegis/
├── backend/
│   ├── requirements.txt
│   ├── data_generator.py          # synthetic data for both personas
│   ├── audit_store.py             # audit log + model_lineage (file-backed SQLite)
│   ├── main.py                    # FastAPI app & all endpoints
│   ├── artifacts/                 # persisted joblib models + JSON lineage sidecars
│   ├── models/
│   │   ├── fraud_spike.py         # Module 1
│   │   ├── return_scorer.py       # Module 2 (calibrated, temporal, SHAP)
│   │   ├── abuse_sentinel.py      # Module 3 (weighted graph, Louvain, PPR)
│   │   └── chargeback_responder.py# Module 4 (calibrated, temporal, coefficients)
│   └── services/
│       ├── splitting.py           # temporal (day-based) train/val/test split
│       ├── calibration.py         # Platt calibration + Brier/reliability diagram
│       ├── model_lineage.py       # joblib persistence + lineage records
│       ├── threshold_sweep.py     # cost-aware threshold curve
│       └── chat_copilot.py        # grounded explainer + LLM/template
├── frontend/
│   ├── package.json / vite.config.js / tailwind.config.js
│   ├── index.html
│   └── src/
│       ├── App.jsx, main.jsx, index.css
│       ├── services/{api.js, mockData.js}
│       └── components/
│           ├── Navbar.jsx, DisclaimerBanner.jsx
│           ├── MetricsDashboard.jsx, RiskSlider.jsx
│           ├── TransactionScorer.jsx, AbuseGraphView.jsx
│           ├── ChargebackPanel.jsx, AuditLogTable.jsx
│           └── ChatCopilotDrawer.jsx
└── README.md
```

---

## ▶️ Run Locally

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

If the backend is not running on `localhost:8000`, configure:

```text
VITE_API_BASE_URL
```

Optional LLM support can be enabled using:

```text
ANTHROPIC_API_KEY
OPENAI_API_KEY
GEMINI_API_KEY
```

Without an API key, the copilot uses its deterministic fallback.

---

## 🔌 Key API Endpoints

| Endpoint                         | Purpose                       |
| -------------------------------- | ----------------------------- |
| `GET /personas`                  | List merchant personas        |
| `POST /personas/switch`          | Switch merchant persona       |
| `GET /dashboard/metrics`         | Model evaluation metrics      |
| `GET /dashboard/threshold-sweep` | Cost-aware threshold analysis |
| `GET /graph/abuse-rings`         | Abuse-ring graph data         |
| `POST /analyze/transaction`      | Score a transaction           |
| `POST /analyze/batch`            | Score CSV transactions        |
| `POST /analyze/dispute`          | Chargeback analysis           |
| `GET /audit/log`                 | Audit trail                   |
| `POST /chat`                     | AI copilot                    |

---

## ⚠️ Scope & Disclaimer

Aegis is a **demonstration / research prototype** using synthetic data.

RTO and chargeback workflows are modeled for demonstration purposes and are **not certified against real PSP, card-network, regulatory, or merchant policies**.

The system provides decision support and does not automatically execute financial, account, or dispute actions.

````

