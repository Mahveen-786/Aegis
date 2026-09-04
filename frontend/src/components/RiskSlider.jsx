import React from 'react';
import { Sliders } from 'lucide-react';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, ReferenceLine } from 'recharts';

export default function RiskSlider({ sweepData, costAssumptions, currentThreshold, onThresholdChange, optimal }) {
  const activeData = sweepData.find((d) => Math.abs(d.threshold - currentThreshold) < 0.03) || sweepData[Math.floor(sweepData.length / 2)] || {};

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 shadow-lg">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-sm font-semibold text-white flex items-center gap-2">
            <Sliders className="w-4 h-4 text-blue-400" />
            Risk Appetite & Cost Optimizer
          </h2>
          <p className="text-xs text-gray-400">
            Return-risk scorer only. Costs are stated assumptions (₹{costAssumptions?.false_positive_cost ?? '—'} per
            false positive, ₹{costAssumptions?.false_negative_cost ?? '—'} per false negative) — swap in real numbers
            for production use.
          </p>
        </div>
        <div className="text-right shrink-0">
          <span className="text-xs text-gray-400">Threshold: </span>
          <span className="text-sm font-bold text-blue-400">{(currentThreshold * 100).toFixed(0)}%</span>
          {optimal && (
            <button
              onClick={() => onThresholdChange(optimal.threshold)}
              className="block text-[10px] text-emerald-400 hover:text-emerald-300 mt-0.5"
              title="Set threshold to the point that minimizes total stated cost"
            >
              Optimal: {(optimal.threshold * 100).toFixed(0)}% (₹{optimal.total_loss_inr.toLocaleString()})
            </button>
          )}
        </div>
      </div>

      <input
        type="range"
        min="0.10"
        max="0.90"
        step="0.05"
        value={currentThreshold}
        onChange={(e) => onThresholdChange(parseFloat(e.target.value))}
        className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500 my-3"
      />
      <div className="flex justify-between text-[11px] text-gray-500 mb-4">
        <span>Aggressive (catch more risk)</span>
        <span>Balanced</span>
        <span>Conservative (less friction)</span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
        <div className="bg-gray-800/60 p-3 rounded-lg border border-gray-700/50">
          <span className="text-xs text-gray-400">Precision</span>
          <p className="text-lg font-bold text-emerald-400">{((activeData.precision || 0) * 100).toFixed(1)}%</p>
        </div>
        <div className="bg-gray-800/60 p-3 rounded-lg border border-gray-700/50">
          <span className="text-xs text-gray-400">Recall</span>
          <p className="text-lg font-bold text-blue-400">{((activeData.recall || 0) * 100).toFixed(1)}%</p>
        </div>
        <div className="bg-gray-800/60 p-3 rounded-lg border border-gray-700/50">
          <span className="text-xs text-gray-400">FP Cost</span>
          <p className="text-lg font-bold text-amber-400">₹{(activeData.cost_fp_inr || 0).toLocaleString()}</p>
        </div>
        <div className="bg-gray-800/60 p-3 rounded-lg border border-gray-700/50">
          <span className="text-xs text-gray-400">FN Cost</span>
          <p className="text-lg font-bold text-orange-400">₹{(activeData.cost_fn_inr || 0).toLocaleString()}</p>
        </div>
        <div className="bg-gray-800/60 p-3 rounded-lg border border-gray-700/50">
          <span className="text-xs text-gray-400">Total Cost</span>
          <p className="text-lg font-bold text-red-400">₹{(activeData.total_loss_inr || 0).toLocaleString()}</p>
        </div>
      </div>

      <div className="h-44 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={sweepData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
            <XAxis dataKey="threshold" stroke="#6b7280" tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} />
            <YAxis stroke="#6b7280" tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`} />
            <Tooltip contentStyle={{ backgroundColor: '#111827', borderColor: '#374151', fontSize: '12px' }} />
            <ReferenceLine x={currentThreshold} stroke="#3b82f6" strokeDasharray="3 3" />
            <Line type="monotone" dataKey="total_loss_inr" name="Total cost (INR)" stroke="#ef4444" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="cost_fp_inr" name="FP cost (INR)" stroke="#f59e0b" strokeWidth={1.5} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
