import React from 'react';
import { Gauge } from 'lucide-react';

const MODULE_LABELS = {
  fraud_spike_detector: 'Fraud-Spike Detector',
  return_risk_scorer: 'Return-Risk Scorer',
  abuse_ring_sentinel: 'Abuse-Ring Sentinel',
  chargeback_evidence_responder: 'Chargeback Evidence Responder',
};

const PROTOCOL_LABELS = {
  held_out_test_split: 'Held-out test split',
  full_window_vs_seeded_ground_truth: 'Full-window vs. seeded ground truth',
  full_graph_vs_seeded_ground_truth: 'Full-graph vs. seeded ground truth',
};

function sampleSizeLine(m) {
  if (m.n_test != null) {
    const base = m.base_rate_test != null ? ` · positive rate ${(m.base_rate_test * 100).toFixed(1)}%` : '';
    return `Test N = ${m.n_test.toLocaleString()}${base}`;
  }
  if (m.n_days != null) {
    return `${m.n_days} days · ${m.n_true_spike_days} seeded spike days`;
  }
  if (m.n_customers_total != null) {
    return `${m.n_customers_total.toLocaleString()} customers · ${m.n_true_ring_members} seeded ring members`;
  }
  return null;
}

function MetricCard({ label, m }) {
  if (!m || m.error) {
    return (
      <div className="bg-gray-800/60 p-3 rounded-lg border border-gray-700/50">
        <p className="text-xs text-gray-400">{label}</p>
        <p className="text-xs text-amber-400 mt-2">{m?.error || 'No metrics available'}</p>
      </div>
    );
  }
  const sampleLine = sampleSizeLine(m);
  return (
    <div className="bg-gray-800/60 p-3 rounded-lg border border-gray-700/50">
      <p className="text-xs text-gray-400 mb-1">{label}</p>
      <p className="text-lg font-bold text-white">F1 {m.f1?.toFixed(2)}</p>
      <p className="text-[11px] text-gray-500 mt-1">
        P {m.precision?.toFixed(2)} · R {m.recall?.toFixed(2)}
        {m.roc_auc != null && <> · AUC {m.roc_auc.toFixed(2)}</>}
      </p>
      {m.confusion_matrix && (
        <p className="text-[10px] text-gray-600 mt-1.5 font-mono">
          TP {m.confusion_matrix.tp} · FP {m.confusion_matrix.fp} · FN {m.confusion_matrix.fn} · TN {m.confusion_matrix.tn}
        </p>
      )}
      {sampleLine && <p className="text-[10px] text-gray-500 mt-1.5">{sampleLine}</p>}
      {m.evaluation_protocol && (
        <p className="text-[10px] text-blue-400/80 mt-1">{PROTOCOL_LABELS[m.evaluation_protocol] || m.evaluation_protocol}</p>
      )}
      {m.small_sample_caveat && (
        <p className="text-[10px] text-amber-400/90 mt-1">{m.small_sample_caveat}</p>
      )}
    </div>
  );
}

export default function MetricsDashboard({ metrics }) {
  const modules = metrics || {};
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 shadow-lg">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-sm font-semibold text-white flex items-center gap-2">
            <Gauge className="w-4 h-4 text-emerald-400" />
            Evaluation Results — All Four Modules
          </h2>
          <p className="text-xs text-gray-400">
            Metrics use the evaluation protocol appropriate to each module — supervised classifiers use a held-out
            test split; the anomaly and graph detectors are evaluated against seeded ground truth over their full
            evaluation population. Protocol and sample size are shown on each card.
          </p>
        </div>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {Object.entries(MODULE_LABELS).map(([key, label]) => (
          <MetricCard key={key} label={label} m={modules[key]} />
        ))}
      </div>
    </div>
  );
}
