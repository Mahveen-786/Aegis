import React, { useState } from 'react';
import { FileWarning, Sparkles } from 'lucide-react';

export default function ChargebackPanel({ onAnalyzeDispute, onExplainResult }) {
  const [dispute, setDispute] = useState({
    dispute_id: 'DISP_LIVE_001',
    reason_code: 'unauthorized_transaction',
    amount_inr: 4500,
    has_3ds_auth: false,
    has_carrier_pod: true,
    has_ip_match: false,
    has_terms_acceptance: true,
    prior_dispute_count: 0,
  });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const toggle = (field) => setDispute({ ...dispute, [field]: !dispute[field] });

  const handleRun = async () => {
    setLoading(true);
    try {
      const res = await onAnalyzeDispute(dispute);
      setResult(res);
    } finally {
      setLoading(false);
    }
  };

  const evidenceFields = [
    { key: 'has_3ds_auth', label: '3D-Secure auth logged' },
    { key: 'has_carrier_pod', label: 'Carrier proof-of-delivery on file' },
    { key: 'has_ip_match', label: 'Checkout IP matches history' },
    { key: 'has_terms_acceptance', label: 'Signed refund policy acceptance' },
  ];

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 shadow-lg">
      <div className="mb-4">
        <h2 className="text-sm font-semibold text-white flex items-center gap-2">
          <FileWarning className="w-4 h-4 text-amber-400" />
          Chargeback Evidence Responder
        </h2>
        <p className="text-xs text-gray-400">
          Toggle what's actually on file. The draft only states these facts — it never invents evidence.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mb-4">
        {evidenceFields.map((f) => (
          <label key={f.key} className="flex items-center gap-2 text-xs text-gray-300 bg-gray-800/60 border border-gray-700/50 rounded px-2.5 py-2 cursor-pointer">
            <input type="checkbox" checked={dispute[f.key]} onChange={() => toggle(f.key)} className="accent-blue-500" />
            {f.label}
          </label>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-3 text-xs mb-4">
        <div>
          <label className="text-gray-400 block mb-1">Amount (INR)</label>
          <input type="number" value={dispute.amount_inr}
            onChange={(e) => setDispute({ ...dispute, amount_inr: parseFloat(e.target.value) })}
            className="w-full bg-gray-800 border border-gray-700 rounded p-2 text-white" />
        </div>
        <div>
          <label className="text-gray-400 block mb-1">Prior disputes (this customer)</label>
          <input type="number" value={dispute.prior_dispute_count}
            onChange={(e) => setDispute({ ...dispute, prior_dispute_count: parseInt(e.target.value, 10) })}
            className="w-full bg-gray-800 border border-gray-700 rounded p-2 text-white" />
        </div>
      </div>

      <button onClick={handleRun} disabled={loading}
        className="w-full py-2 bg-amber-600 hover:bg-amber-500 font-semibold text-xs rounded-lg transition text-white">
        {loading ? 'Evaluating…' : 'Evaluate Dispute'}
      </button>

      {result && (
        <div className="mt-4 p-4 bg-gray-950/70 border border-gray-800 rounded-lg">
          <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-[11px] px-2 py-1 rounded bg-gray-800 border border-gray-700 text-gray-300">
                Model: {((result.model_win_probability ?? result.win_probability) * 100).toFixed(0)}% estimated win likelihood
              </span>
              <span className={`text-[11px] px-2 py-1 rounded font-bold border ${
                result.policy_decision === 'contest'
                  ? 'bg-emerald-950 text-emerald-400 border-emerald-800'
                  : 'bg-red-950 text-red-400 border-red-800'
              }`}>
                Policy: {result.policy_decision === 'contest' ? 'Contest' : 'Accept liability'}
                {result.policy_contest_threshold != null && ` (threshold ${(result.policy_contest_threshold * 100).toFixed(0)}%)`}
              </span>
            </div>
            <button onClick={() => onExplainResult(result)} className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1">
              <Sparkles className="w-3.5 h-3.5" /> Explain this
            </button>
          </div>
          <p className="text-[11px] text-gray-500 mb-2 italic">
            The model estimates win likelihood only. Whether to contest at that likelihood is a separate policy
            decision applied on top — shown here explicitly rather than implied as one combined "AI decision."
          </p>
          <p className="text-xs text-gray-300 mb-2">{result.recommendation}</p>
          {result.evidence_draft && (
            <pre className="text-[11px] text-gray-400 whitespace-pre-wrap bg-gray-900 border border-gray-800 rounded p-2 mt-2">{result.evidence_draft}</pre>
          )}
        </div>
      )}
    </div>
  );
}
