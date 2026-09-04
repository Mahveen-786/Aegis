import React, { useState } from 'react';
import { FileText } from 'lucide-react';

const MODULE_LABELS = {
  fraud_spike_detector: 'Fraud-Spike Detector',
  return_risk_scorer: 'Return-Risk Scorer',
  abuse_ring_sentinel: 'Abuse-Ring Sentinel',
  chargeback_evidence_responder: 'Chargeback Responder',
};

export default function AuditLogTable({ logs, moduleCounts, onFilterChange }) {
  const [filter, setFilter] = useState('all');

  const handleFilter = (mod) => {
    setFilter(mod);
    onFilterChange(mod === 'all' ? undefined : mod);
  };

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 shadow-lg">
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-4 gap-3">
        <div>
          <h2 className="text-sm font-semibold text-white flex items-center gap-2">
            <FileText className="w-4 h-4 text-blue-400" />
            Audit Trail
          </h2>
          <p className="text-xs text-gray-400">
            Every scoring event across all four modules, with the evidence that drove it -- separate from the results dashboard.
          </p>
        </div>
        <div className="flex items-center gap-1.5 flex-wrap">
          <button onClick={() => handleFilter('all')}
            className={`text-[11px] px-2 py-1 rounded border ${filter === 'all' ? 'bg-blue-600 border-blue-500 text-white' : 'bg-gray-800 border-gray-700 text-gray-400'}`}>
            All ({Object.values(moduleCounts || {}).reduce((a, b) => a + b, 0)})
          </button>
          {Object.entries(MODULE_LABELS).map(([key, label]) => (
            <button key={key} onClick={() => handleFilter(key)}
              className={`text-[11px] px-2 py-1 rounded border ${filter === key ? 'bg-blue-600 border-blue-500 text-white' : 'bg-gray-800 border-gray-700 text-gray-400'}`}>
              {label} ({moduleCounts?.[key] || 0})
            </button>
          ))}
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs text-gray-300">
          <thead className="bg-gray-800/60 text-gray-400 border-b border-gray-700">
            <tr>
              <th className="p-2.5">Timestamp</th>
              <th className="p-2.5">Target</th>
              <th className="p-2.5">Module</th>
              <th className="p-2.5">Score</th>
              <th className="p-2.5">Decision</th>
              <th className="p-2.5">Recommended Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            {(logs || []).map((log) => (
              <tr key={log.id} className="hover:bg-gray-800/40 transition">
                <td className="p-2.5 text-gray-500 font-mono">{(log.timestamp || '').slice(11, 19)}</td>
                <td className="p-2.5 font-semibold text-white">{log.target_id}</td>
                <td className="p-2.5 text-gray-400">{MODULE_LABELS[log.module_name] || log.module_name}</td>
                <td className="p-2.5">{log.score != null ? `${(log.score * 100).toFixed(0)}%` : '—'}</td>
                <td className="p-2.5">
                  <span className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                    log.flagged ? 'bg-red-950 text-red-400 border border-red-800' : 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                  }`}>
                    {log.flagged ? 'Flagged' : 'Passed'}
                  </span>
                </td>
                <td className="p-2.5 text-gray-400">{log.action_recommended}</td>
              </tr>
            ))}
            {(!logs || logs.length === 0) && (
              <tr><td colSpan={6} className="p-4 text-center text-gray-500">No audit entries yet — score a transaction, dispute, or upload a batch to populate the trail.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
