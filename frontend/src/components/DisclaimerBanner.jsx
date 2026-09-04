import React from 'react';
import { AlertTriangle, Shield } from 'lucide-react';

export default function DisclaimerBanner() {
  return (
    <div className="bg-gray-900/60 border border-gray-800 rounded-lg p-3 my-4 flex flex-col md:flex-row items-start md:items-center justify-between text-xs text-gray-400 gap-2">
      <div className="flex items-center gap-2">
        <Shield className="w-4 h-4 text-blue-400 shrink-0" />
        <span>
          <strong className="text-gray-200">Strictly defense-only:</strong> every module here produces a flag, score, or
          drafting aid for a human reviewer. Nothing in this system sends messages, submits disputes, blocks accounts,
          or takes any action autonomously.
        </span>
      </div>
      <div className="flex items-center gap-2 text-gray-500">
        <AlertTriangle className="w-3.5 h-3.5 text-amber-500 shrink-0" />
        <span>
          RTO / dispute-representment framing is <strong className="text-gray-300">modeled on</strong> how those
          mechanisms work for an Indian BFSI context -- <strong className="text-gray-300">not</strong> a claim of
          certification or compliance with any card network's or PSP's actual official rules.
        </span>
      </div>
    </div>
  );
}
