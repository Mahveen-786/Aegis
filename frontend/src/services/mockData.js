// Offline demo data -- used only when the backend is unreachable, so a
// cold-start free-tier deployment can't break a live judging session.
// Shapes intentionally mirror the real /dashboard/metrics, /dashboard/threshold-sweep,
// /graph/abuse-rings, and /audit/log responses.

export const MOCK_DATA = {
  personas: {
    active: 'apparel',
    available: {
      apparel: { name: 'Merchant A: D2C Apparel Brand', focus: 'High RTO & COD Risk' },
      saas: { name: 'Merchant B: Digital SaaS & Electronics', focus: 'High Chargeback & Card Fraud' },
    },
  },

  metrics: {
    fraud_spike_detector: { precision: 0.80, recall: 1.0, f1: 0.889 },
    return_risk_scorer: { precision: 0.53, recall: 0.81, f1: 0.64, roc_auc: 0.78, operating_threshold: 0.16 },
    abuse_ring_sentinel: { precision: 0.73, recall: 1.0, f1: 0.84 },
    chargeback_evidence_responder: { precision: 0.70, recall: 0.74, f1: 0.72, roc_auc: 0.86 },
  },

  sweep: [
    { threshold: 0.10, precision: 0.30, recall: 0.95, cost_fp_inr: 42000, cost_fn_inr: 8000, total_loss_inr: 50000 },
    { threshold: 0.25, precision: 0.45, recall: 0.86, cost_fp_inr: 24000, cost_fn_inr: 21000, total_loss_inr: 45000 },
    { threshold: 0.40, precision: 0.55, recall: 0.75, cost_fp_inr: 15000, cost_fn_inr: 37000, total_loss_inr: 52000 },
    { threshold: 0.55, precision: 0.68, recall: 0.60, cost_fp_inr: 9000, cost_fn_inr: 58000, total_loss_inr: 67000 },
    { threshold: 0.70, precision: 0.80, recall: 0.42, cost_fp_inr: 4500, cost_fn_inr: 89000, total_loss_inr: 93500 },
    { threshold: 0.85, precision: 0.91, recall: 0.20, cost_fp_inr: 1200, cost_fn_inr: 128000, total_loss_inr: 129200 },
  ],
  cost_assumptions_inr: { false_positive_cost: 20, false_negative_cost: 350 },
  optimal_threshold: { threshold: 0.25, precision: 0.45, recall: 0.86, cost_fp_inr: 24000, cost_fn_inr: 21000, total_loss_inr: 45000 },

  clusters: [
    { cluster_id: 'RING_000', customer_count: 6, customers: ['CUST_APP_00001', 'CUST_APP_00002'], shared_identifiers: ['DEV:DEV_RING_APP_000', 'IP:10.4.12.9'] },
  ],
  cytoscape_elements: [],

  audit: {
    module_counts: { fraud_spike_detector: 1, return_risk_scorer: 3, abuse_ring_sentinel: 2, chargeback_evidence_responder: 1 },
    logs: [
      {
        id: 1, timestamp: new Date().toISOString(), persona: 'apparel',
        target_id: 'TXN_DEMO_001', target_type: 'transaction', module_name: 'return_risk_scorer',
        score: 0.82, threshold_applied: 0.16, flagged: true,
        evidence: { factors: [{ feature: 'Payment Method', value: 'COD', impact: 'Higher RTO likelihood' }] },
        action_recommended: 'Trigger OTP / pre-dispatch address confirmation for human review',
      },
    ],
  },
};
