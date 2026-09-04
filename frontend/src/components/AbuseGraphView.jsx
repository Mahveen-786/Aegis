import React, { useEffect, useRef } from 'react';
import cytoscape from 'cytoscape';
import { Network } from 'lucide-react';

export default function AbuseGraphView({ clusters, elements, metrics }) {
  const containerRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current || !elements || elements.length === 0) return;
    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        { selector: 'node[type="customer"]', style: { 'background-color': '#3b82f6', label: 'data(label)', color: '#cbd5e1', 'font-size': '9px', width: 20, height: 20 } },
        { selector: 'node[type="device"], node[type="ip"], node[type="address"]', style: { 'background-color': '#ef4444', label: 'data(label)', color: '#f87171', 'font-size': '8px', width: 16, height: 16 } },
        { selector: 'edge', style: { width: 1.5, 'line-color': '#475569', 'curve-style': 'bezier' } },
      ],
      layout: { name: 'cose', animate: false },
    });
    return () => cy.destroy();
  }, [elements]);

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 shadow-lg">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h2 className="text-sm font-semibold text-white flex items-center gap-2">
            <Network className="w-4 h-4 text-purple-400" />
            Abuse-Ring Sentinel
          </h2>
          <p className="text-xs text-gray-400">Shared device / IP / address clusters. {metrics && (
            <>Precision {metrics.precision?.toFixed(2)} · Recall {metrics.recall?.toFixed(2)}</>
          )}</p>
        </div>
        <span className="text-xs bg-purple-950 border border-purple-800 text-purple-300 px-2.5 py-1 rounded-full">
          {clusters?.length || 0} rings
        </span>
      </div>

      {elements && elements.length > 0 ? (
        <div ref={containerRef} className="h-64 w-full bg-gray-950 rounded-lg border border-gray-800" />
      ) : (
        <div className="h-64 w-full bg-gray-950 rounded-lg border border-gray-800 flex items-center justify-center text-xs text-gray-500">
          No cluster graph data available (offline mode has limited graph data).
        </div>
      )}

      <div className="mt-3 flex items-center gap-4 text-xs text-gray-400">
        <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 bg-blue-500 rounded-full inline-block" /> Customer accounts</span>
        <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 bg-red-500 rounded-full inline-block" /> Shared device / IP / address</span>
      </div>
    </div>
  );
}
