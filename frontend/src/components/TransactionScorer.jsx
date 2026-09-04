import React, { useState, useRef } from 'react';
import { Play, Sparkles, Upload } from 'lucide-react';

const DEMO_SAMPLES = [
  {
    name: 'Normal Order',
    data: { transaction_id: 'TXN_OK_01', customer_id: 'CUST_APP_00120', amount_inr: 1200, category: 'T-Shirts', payment_method: 'UPI', discount_pct: 10, account_age_days: 180, cust_return_rate: 0.08, day_offset: 10 },
  },
  {
    name: 'High RTO COD Order',
    data: { transaction_id: 'TXN_RTO_99', customer_id: 'CUST_APP_00884', amount_inr: 2899, category: 'Footwear', payment_method: 'COD', discount_pct: 45, account_age_days: 2, cust_return_rate: 0.65, day_offset: 21 },
  },
  {
    name: 'Card-Testing Fraud Pattern',
    data: { transaction_id: 'TXN_FRAUD_07', customer_id: 'CUST_APP_00099', amount_inr: 4500, category: 'Dresses', payment_method: 'Credit Card', discount_pct: 5, account_age_days: 1, cust_return_rate: 0.05, day_offset: 22 },
  },
];

export default function TransactionScorer({ onScoreTxn, onScoreBatch, onExplainResult, threshold }) {
  const [formData, setFormData] = useState(DEMO_SAMPLES[1].data);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [batchResult, setBatchResult] = useState(null);
  const [batchError, setBatchError] = useState(null);
  const fileInputRef = useRef(null);

  const handleRun = async (dataToRun) => {
    setLoading(true);
    const data = dataToRun || formData;
    try {
      const res = await onScoreTxn(data);
      setResult(res);
      setBatchResult(null);
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true);
    setBatchError(null);
    try {
      const res = await onScoreBatch(file);
      setBatchResult(res);
      setResult(null);
    } catch (err) {
      setBatchError(err?.response?.data?.detail || 'Could not process this CSV.');
    } finally {
      setLoading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 shadow-lg">
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-4 gap-3">
        <div>
          <h2 className="text-sm font-semibold text-white flex items-center gap-2">
            <Play className="w-4 h-4 text-emerald-400" />
            Transaction Evaluation Sandbox
          </h2>
          <p className="text-xs text-gray-400">Score a single order, or upload a CSV for batch scoring.</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {DEMO_SAMPLES.map((sample) => (
            <button
              key={sample.name}
              onClick={() => { setFormData(sample.data); handleRun(sample.data); }}
              className="text-xs px-2.5 py-1 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-300 rounded-md transition"
            >
              {sample.name}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs mb-4">
        <div>
          <label className="text-gray-400 block mb-1">Amount (INR)</label>
          <input type="number" value={formData.amount_inr}
            onChange={(e) => setFormData({ ...formData, amount_inr: parseFloat(e.target.value) })}
            className="w-full bg-gray-800 border border-gray-700 rounded p-2 text-white" />
        </div>
        <div>
          <label className="text-gray-400 block mb-1">Payment Method</label>
          <select value={formData.payment_method}
            onChange={(e) => setFormData({ ...formData, payment_method: e.target.value })}
            className="w-full bg-gray-800 border border-gray-700 rounded p-2 text-white">
            <option value="COD">COD (Cash on Delivery)</option>
            <option value="UPI">UPI</option>
            <option value="Credit Card">Credit Card</option>
            <option value="Debit Card">Debit Card</option>
          </select>
        </div>
        <div>
          <label className="text-gray-400 block mb-1">Discount %</label>
          <input type="number" value={formData.discount_pct}
            onChange={(e) => setFormData({ ...formData, discount_pct: parseFloat(e.target.value) })}
            className="w-full bg-gray-800 border border-gray-700 rounded p-2 text-white" />
        </div>
        <div>
          <label className="text-gray-400 block mb-1">Account Age (days)</label>
          <input type="number" value={formData.account_age_days}
            onChange={(e) => setFormData({ ...formData, account_age_days: parseInt(e.target.value, 10) })}
            className="w-full bg-gray-800 border border-gray-700 rounded p-2 text-white" />
        </div>
      </div>

      <div className="flex gap-2">
        <button onClick={() => handleRun()} disabled={loading}
          className="flex-1 py-2 bg-blue-600 hover:bg-blue-500 font-semibold text-xs rounded-lg transition text-white">
          {loading ? 'Scoring…' : 'Score Transaction'}
        </button>
        <label className="flex items-center gap-1.5 px-3 py-2 bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-lg text-xs text-gray-300 cursor-pointer transition">
          <Upload className="w-3.5 h-3.5" />
          Upload CSV
          <input ref={fileInputRef} type="file" accept=".csv" className="hidden" onChange={handleFileUpload} />
        </label>
      </div>

      {batchError && <p className="text-xs text-red-400 mt-2">{batchError}</p>}

      {result && (
        <div className="mt-4 p-4 bg-gray-950/70 border border-gray-800 rounded-lg">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-bold text-gray-300">Result:</span>
            <button onClick={() => onExplainResult(result.return_risk)}
              className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1">
              <Sparkles className="w-3.5 h-3.5" /> Explain this
            </button>
          </div>
          <div className="flex items-center gap-3 flex-wrap">
            <span className={`text-sm px-2.5 py-1 rounded font-bold ${
              result.return_risk.is_flagged ? 'bg-red-950 text-red-400 border border-red-800' : 'bg-emerald-950 text-emerald-400 border border-emerald-800'
            }`}>
              Return risk: {(result.return_risk.score * 100).toFixed(0)}% ({result.return_risk.risk_level})
            </span>
            {result.abuse_ring?.in_ring && (
              <span className="text-sm px-2.5 py-1 rounded font-bold bg-purple-950 text-purple-300 border border-purple-800">
                Abuse ring: cluster of {result.abuse_ring.cluster_size}
                {result.abuse_ring.evidence_breakdown && (
                  <span className="font-normal text-[11px] ml-1.5">
                    (device ×{result.abuse_ring.evidence_breakdown.shared_device},
                    {' '}IP ×{result.abuse_ring.evidence_breakdown.shared_ip},
                    {' '}address ×{result.abuse_ring.evidence_breakdown.shared_address})
                  </span>
                )}
              </span>
            )}
            {result.fraud_spike_day_check?.is_spike && (
              <span className="text-sm px-2.5 py-1 rounded font-bold bg-amber-950 text-amber-300 border border-amber-800">
                Fraud-spike day
              </span>
            )}
          </div>
          {result.return_risk.contributing_factors?.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {result.return_risk.contributing_factors.map((f, i) => (
                <span key={i} className="text-[11px] bg-gray-800 px-2 py-0.5 rounded text-gray-300 border border-gray-700">
                  {f.feature}: <strong>{f.value}</strong> ({f.impact})
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {batchResult && (
        <div className="mt-4 p-4 bg-gray-950/70 border border-gray-800 rounded-lg">
          <p className="text-xs font-bold text-gray-300 mb-2">
            Batch result: {batchResult.n_rows} rows scored, {batchResult.results.filter((r) => r.return_risk.is_flagged).length} flagged
          </p>
          <div className="max-h-48 overflow-y-auto space-y-1">
            {batchResult.results.map((r) => (
              <div key={r.transaction_id} className="flex items-center justify-between text-xs text-gray-400 border-b border-gray-800 py-1">
                <span className="font-mono">{r.transaction_id}</span>
                <span className={r.return_risk.is_flagged ? 'text-red-400' : 'text-emerald-400'}>
                  {(r.return_risk.score * 100).toFixed(0)}% — {r.return_risk.is_flagged ? 'Flagged' : 'Clear'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
