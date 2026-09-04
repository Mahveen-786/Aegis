import axios from 'axios';
import { MOCK_DATA } from './mockData';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

async function withFallback(liveCall, mockValue) {
  try {
    const result = await liveCall();
    apiClient.lastCallUsedFallback = false;
    return result;
  } catch (err) {
    // IMPORTANT: this fallback fires silently from the caller's perspective --
    // the flag below is how the UI knows to show "showing demo data" instead
    // of quietly presenting mock numbers as if they were live.
    apiClient.lastCallUsedFallback = true;
    return mockValue;
  }
}

export const apiClient = {
  isOffline: false,
  lastCallUsedFallback: false,

  async getPersonas() {
    if (this.isOffline) return MOCK_DATA.personas;
    return withFallback(async () => (await axios.get(`${BASE_URL}/personas`)).data, MOCK_DATA.personas);
  },

  async switchPersona(persona) {
    if (this.isOffline) return { active_persona: persona };
    return withFallback(
      async () => (await axios.post(`${BASE_URL}/personas/switch?persona=${persona}`)).data,
      { active_persona: persona }
    );
  },

  async getMetrics() {
    if (this.isOffline) return { modules: MOCK_DATA.metrics };
    return withFallback(async () => (await axios.get(`${BASE_URL}/dashboard/metrics`)).data, { modules: MOCK_DATA.metrics });
  },

  async getThresholdSweep() {
    const mock = { curve: MOCK_DATA.sweep, cost_assumptions_inr: MOCK_DATA.cost_assumptions_inr, optimal: MOCK_DATA.optimal_threshold };
    if (this.isOffline) return mock;
    return withFallback(async () => (await axios.get(`${BASE_URL}/dashboard/threshold-sweep`)).data, mock);
  },

  async getAbuseRings() {
    if (this.isOffline) return { clusters: MOCK_DATA.clusters, cytoscape_elements: MOCK_DATA.cytoscape_elements };
    return withFallback(
      async () => (await axios.get(`${BASE_URL}/graph/abuse-rings`)).data,
      { clusters: MOCK_DATA.clusters, cytoscape_elements: MOCK_DATA.cytoscape_elements }
    );
  },

  async analyzeTransaction(txnData, threshold) {
    if (this.isOffline) {
      const isCod = txnData.payment_method === 'COD';
      return {
        transaction_id: txnData.transaction_id,
        return_risk: {
          score: isCod ? 0.78 : 0.22,
          is_flagged: isCod,
          risk_level: isCod ? 'High' : 'Low',
          contributing_factors: isCod
            ? [{ feature: 'Payment Method', value: 'COD', impact: 'Higher RTO likelihood' }]
            : [{ feature: 'Baseline', value: 'No elevated risk factors detected', impact: 'Within normal range' }],
          recommended_action: isCod ? 'Trigger OTP / pre-dispatch address confirmation for human review' : 'No extra verification needed',
        },
        abuse_ring: { in_ring: false, cluster_size: 0, shared_entities: [], recommended_action: 'No shared-identity signal found' },
        fraud_spike_day_check: { is_spike: false, z_score: 0.4, fraud_rate: 0.01 },
      };
    }
    const params = threshold != null ? `?threshold=${threshold}` : '';
    const res = await axios.post(`${BASE_URL}/analyze/transaction${params}`, txnData);
    return res.data;
  },

  async analyzeBatch(file, threshold) {
    const form = new FormData();
    form.append('file', file);
    const params = threshold != null ? `?threshold=${threshold}` : '';
    const res = await axios.post(`${BASE_URL}/analyze/batch${params}`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },

  async loadDemoDataset(limit = 25) {
    if (this.isOffline) return { n_total_transactions: 40000, sample_size: 0, sample: [] };
    return withFallback(
      async () => (await axios.get(`${BASE_URL}/analyze/demo-dataset?limit=${limit}`)).data,
      { n_total_transactions: 40000, sample_size: 0, sample: [] }
    );
  },

  async analyzeDispute(disputeData) {
    if (this.isOffline) {
      const winProb = disputeData.has_carrier_pod ? 0.62 : 0.28;
      return {
        dispute_id: disputeData.dispute_id,
        model_win_probability: winProb,
        policy_contest_threshold: 0.6,
        policy_decision: winProb >= 0.6 ? 'contest' : 'accept_liability',
        win_probability: winProb,
        recommendation: disputeData.has_carrier_pod ? 'Evidence supports contesting this dispute.' : 'Evidence is weak; consider accepting the chargeback rather than contesting.',
        evidence_present: disputeData.has_carrier_pod ? ['carrier proof-of-delivery on file'] : [],
        evidence_missing: disputeData.has_carrier_pod ? [] : ['no carrier proof-of-delivery on file'],
      };
    }
    const res = await axios.post(`${BASE_URL}/analyze/dispute`, disputeData);
    return res.data;
  },

  async getAuditLog(moduleFilter) {
    if (this.isOffline) return MOCK_DATA.audit;
    const params = moduleFilter ? `?module=${moduleFilter}` : '';
    return withFallback(async () => (await axios.get(`${BASE_URL}/audit/log${params}`)).data, MOCK_DATA.audit);
  },

  async askCopilot(query, contextResult) {
    if (this.isOffline) {
      return {
        reply: '[Offline demo mode] The Aegis Copilot needs a live backend connection to explain grounded results. ' +
               'Glossary answers still work: try asking "what is RTO?" or "what is a chargeback?".',
        source: 'offline',
      };
    }
    const res = await axios.post(`${BASE_URL}/chat`, { query, context_result: contextResult });
    return res.data;
  },
};
