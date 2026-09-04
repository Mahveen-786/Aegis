import React, { useState, useEffect, useCallback } from 'react';
import Navbar from './components/Navbar';
import DisclaimerBanner from './components/DisclaimerBanner';
import MetricsDashboard from './components/MetricsDashboard';
import RiskSlider from './components/RiskSlider';
import TransactionScorer from './components/TransactionScorer';
import AbuseGraphView from './components/AbuseGraphView';
import ChargebackPanel from './components/ChargebackPanel';
import AuditLogTable from './components/AuditLogTable';
import ChatCopilotDrawer from './components/ChatCopilotDrawer';
import { apiClient } from './services/api';

export default function App() {
  const [activePersona, setActivePersona] = useState('apparel');
  const [isOffline, setIsOffline] = useState(false);
  const [usingFallbackData, setUsingFallbackData] = useState(false);

  const [metrics, setMetrics] = useState({});
  const [threshold, setThreshold] = useState(0.5);
  const [sweepData, setSweepData] = useState([]);
  const [costAssumptions, setCostAssumptions] = useState({});
  const [optimalThreshold, setOptimalThreshold] = useState(null);
  const [clusters, setClusters] = useState([]);
  const [elements, setElements] = useState([]);
  const [abuseMetrics, setAbuseMetrics] = useState(null);

  const [auditLogs, setAuditLogs] = useState([]);
  const [moduleCounts, setModuleCounts] = useState({});

  const [copilotOpen, setCopilotOpen] = useState(false);
  const [selectedContext, setSelectedContext] = useState(null);

  const loadData = useCallback(async (moduleFilter) => {
    const m = await apiClient.getMetrics();
    setMetrics(m.modules || {});

    const sweep = await apiClient.getThresholdSweep();
    setSweepData(sweep.curve || []);
    setCostAssumptions(sweep.cost_assumptions_inr || {});
    setOptimalThreshold(sweep.optimal || null);

    const rings = await apiClient.getAbuseRings();
    setClusters(rings.clusters || []);
    setElements(rings.cytoscape_elements || []);
    setAbuseMetrics(rings.metrics || null);

    const audit = await apiClient.getAuditLog(moduleFilter);
    setAuditLogs(audit.logs || []);
    setModuleCounts(audit.module_counts || {});

    // If the user is in Live API Mode but a call silently fell back to mock
    // data (backend down, cold start, etc.), surface that -- never let
    // fallback data masquerade as live.
    setUsingFallbackData(!apiClient.isOffline && apiClient.lastCallUsedFallback);
  }, []);

  useEffect(() => {
    apiClient.isOffline = isOffline;
    loadData();
  }, [activePersona, isOffline, loadData]);

  const handleSelectPersona = async (persona) => {
    // Switch the backend's active persona FIRST, then update local state --
    // otherwise the loadData() triggered by the state change can race ahead
    // of the backend switch and briefly show the new persona's label next to
    // the old persona's data.
    await apiClient.switchPersona(persona);
    setActivePersona(persona);
  };

  const handleScoreTxn = async (txn) => {
    const res = await apiClient.analyzeTransaction(txn, threshold);
    loadData();
    return res;
  };

  const handleScoreBatch = async (file) => {
    const res = await apiClient.analyzeBatch(file, threshold);
    loadData();
    return res;
  };

  const handleAnalyzeDispute = async (dispute) => {
    const res = await apiClient.analyzeDispute(dispute);
    loadData();
    return res;
  };

  const handleExplain = (context) => {
    setSelectedContext(context);
    setCopilotOpen(true);
  };

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex flex-col">
      <Navbar
        activePersona={activePersona}
        onSelectPersona={handleSelectPersona}
        isOffline={isOffline}
        setIsOffline={setIsOffline}
        usingFallbackData={usingFallbackData}
      />

      <main className="max-w-7xl mx-auto px-4 py-4 flex-1 w-full space-y-6">
        <DisclaimerBanner />

        <MetricsDashboard metrics={metrics} />

        <RiskSlider
          sweepData={sweepData}
          costAssumptions={costAssumptions}
          currentThreshold={threshold}
          onThresholdChange={setThreshold}
          optimal={optimalThreshold}
        />

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <TransactionScorer
            onScoreTxn={handleScoreTxn}
            onScoreBatch={handleScoreBatch}
            onExplainResult={handleExplain}
            threshold={threshold}
          />
          <AbuseGraphView clusters={clusters} elements={elements} metrics={abuseMetrics} />
        </div>

        <ChargebackPanel onAnalyzeDispute={handleAnalyzeDispute} onExplainResult={handleExplain} />

        <AuditLogTable
          logs={auditLogs}
          moduleCounts={moduleCounts}
          onFilterChange={(mod) => loadData(mod)}
        />
      </main>

      <ChatCopilotDrawer
        isOpen={copilotOpen}
        onClose={() => setCopilotOpen(false)}
        selectedContext={selectedContext}
        onAskCopilot={(q, ctx) => apiClient.askCopilot(q, ctx)}
      />

      {!copilotOpen && (
        <button
          onClick={() => { setSelectedContext(null); setCopilotOpen(true); }}
          className="fixed bottom-5 right-5 bg-blue-600 hover:bg-blue-500 text-white rounded-full p-4 shadow-lg z-40"
          title="Open Aegis Copilot"
        >
          💬
        </button>
      )}
    </div>
  );
}
