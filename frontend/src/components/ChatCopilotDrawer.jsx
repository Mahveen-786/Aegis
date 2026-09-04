import React, { useState } from 'react';
import { Sparkles, Send, X } from 'lucide-react';

export default function ChatCopilotDrawer({ isOpen, onClose, selectedContext, onAskCopilot }) {
  const [messages, setMessages] = useState([
    { role: 'assistant', text: 'Hi! I\'m the Aegis Copilot. Ask me glossary questions ("What is RTO?", "What is a chargeback?"), or click "Explain this" on any result and I\'ll walk through it.' },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSend = async (textToSend) => {
    const query = textToSend || input;
    if (!query.trim()) return;
    const newMsgs = [...messages, { role: 'user', text: query }];
    setMessages(newMsgs);
    setInput('');
    setLoading(true);
    try {
      const res = await onAskCopilot(query, selectedContext);
      setMessages([...newMsgs, { role: 'assistant', text: res.reply, source: res.source, intent: res.intent }]);
    } catch {
      setMessages([...newMsgs, { role: 'assistant', text: 'Something went wrong reaching the copilot. Try again in a moment.' }]);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-y-0 right-0 w-full max-w-sm bg-gray-900 border-l border-gray-800 shadow-2xl z-50 flex flex-col">
      <div className="p-4 border-b border-gray-800 flex items-center justify-between bg-gray-950">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-blue-400" />
          <h3 className="text-sm font-bold text-white">Explainable Risk Copilot</h3>
        </div>
        <button onClick={onClose} className="text-gray-400 hover:text-white"><X className="w-4 h-4" /></button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3 text-xs">
        {messages.map((m, idx) => (
          <div key={idx} className={`p-3 rounded-lg ${
            m.intent === 'out_of_scope' ? 'bg-amber-950/40 border border-amber-800 text-amber-200' :
            m.role === 'assistant' ? 'bg-gray-800 border border-gray-700 text-gray-200' : 'bg-blue-600 text-white ml-6'
          }`}>
            {m.intent === 'out_of_scope' && <div className="text-[10px] font-bold text-amber-400 mb-1">OUTSIDE DEMO SCOPE</div>}
            <div className="whitespace-pre-line">{m.text}</div>
            {m.source && <div className="text-[10px] text-gray-500 mt-1">source: {m.source}</div>}
          </div>
        ))}
        {loading && <div className="text-gray-500 text-xs italic">Thinking…</div>}
      </div>

      <div className="p-3 border-t border-gray-800 bg-gray-950 flex gap-2">
        <input type="text" value={input} onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          placeholder="Ask why something was flagged…"
          className="flex-1 bg-gray-800 border border-gray-700 rounded p-2 text-xs text-white" />
        <button onClick={() => handleSend()} className="p-2 bg-blue-600 rounded text-white hover:bg-blue-500">
          <Send className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
