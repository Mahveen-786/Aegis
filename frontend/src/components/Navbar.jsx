import React from 'react';
import { ShieldCheck, Layers, Cpu, AlertTriangle } from 'lucide-react';

export default function Navbar({ activePersona, onSelectPersona, isOffline, setIsOffline, usingFallbackData }) {
  return (
    <header className="bg-gray-900 border-b border-gray-800 sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 py-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center space-x-3">
          <div className="bg-blue-600 p-2 rounded-lg text-white">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-white flex items-center gap-2">
              Aegis
            </h1>
            <p className="text-xs text-gray-400">Strictly defense-only loss prevention</p>
          </div>
        </div>

        <div className="flex items-center space-x-4">
          <div className="flex items-center bg-gray-800 rounded-lg p-1 border border-gray-700">
            <Layers className="w-4 h-4 text-gray-400 ml-2 mr-1" />
            <button
              onClick={() => onSelectPersona('apparel')}
              className={`px-3 py-1 text-xs font-medium rounded-md transition ${
                activePersona === 'apparel' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'
              }`}
            >
              Merchant A (D2C Apparel)
            </button>
            <button
              onClick={() => onSelectPersona('saas')}
              className={`px-3 py-1 text-xs font-medium rounded-md transition ${
                activePersona === 'saas' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'
              }`}
            >
              Merchant B (SaaS & Electronics)
            </button>
          </div>

          <button
            onClick={() => setIsOffline(!isOffline)}
            className={`flex items-center text-xs px-2.5 py-1.5 rounded-md border ${
              isOffline ? 'bg-amber-950/40 border-amber-700 text-amber-300' : 'bg-emerald-950/40 border-emerald-700 text-emerald-300'
            }`}
            title="Toggle Demo/Offline Mode -- bundled mock responses if the live backend is unreachable"
          >
            <Cpu className="w-3.5 h-3.5 mr-1" />
            {isOffline ? 'Offline Demo Mode' : 'Live API Mode'}
          </button>

          {usingFallbackData && (
            <span
              className="flex items-center text-xs px-2.5 py-1.5 rounded-md border bg-red-950/50 border-red-700 text-red-300 animate-pulse"
              title="A live API call just failed and this data fell back to bundled demo data automatically -- it is NOT live"
            >
              <AlertTriangle className="w-3.5 h-3.5 mr-1" />
              Showing demo data (live call failed)
            </span>
          )}
        </div>
      </div>
    </header>
  );
}
