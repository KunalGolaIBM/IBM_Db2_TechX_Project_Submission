import type { ReactNode } from 'react';
import { CrewFindings } from '../api';
import Badge from './SeverityBadge';
import { Brain, AlertTriangle, ShieldCheck, ListChecks, SearchCheck } from 'lucide-react';

function AgentCard({ label, text }: { label: string; text: string }) {
  if (!text) return null;
  return (
    <div className="bg-navy-800 border border-navy-600 rounded-xl p-5">
      <div className="flex items-center gap-2 mb-3">
        <Brain className="w-4 h-4 text-teal-400" />
        <h3 className="text-white font-medium text-sm">{label}</h3>
      </div>
      <p className="text-slate-300 text-sm whitespace-pre-wrap bg-navy-700 rounded-lg p-3">{text}</p>
    </div>
  );
}

function BulletList({ title, items, icon }: { title: string; items: string[]; icon: ReactNode }) {
  if (!items || items.length === 0) return null;
  return (
    <div className="bg-navy-800 border border-navy-600 rounded-xl p-5">
      <div className="flex items-center gap-2 mb-3">
        {icon}
        <h3 className="text-white font-medium text-sm">{title}</h3>
      </div>
      <ul className="space-y-1.5">
        {items.map((item, i) => (
          <li key={i} className="text-slate-300 text-sm flex gap-2">
            <span className="text-teal-400 mt-0.5">•</span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function CrewAnalysisPanel({ findings }: { findings: CrewFindings }) {
  const isLive = findings.source === 'crewai' && findings.available;
  return (
    <div className="space-y-4">
      {/* Status header */}
      <div className="bg-navy-800 border border-navy-600 rounded-xl p-5">
        <div className="flex items-center gap-2 mb-3 flex-wrap">
          <Brain className="w-5 h-5 text-teal-400" />
          <h2 className="text-white font-semibold">CrewAI Collaborative Analysis</h2>
          <Badge label={isLive ? 'SUCCESS' : 'FALLBACK'} />
          {findings.reused && <Badge label="REUSED" />}
        </div>
        <p className="text-slate-400 text-xs">
          {isLive
            ? 'Live analysis from the Risk Analyst, Domain Expert, and Recommendation Specialist agents.'
            : 'Deterministic fallback built only from stored Db2 facts. The numeric risk score below remains authoritative.'}
          {findings.reused ? ' Reused from the audit log; the model was not re-invoked.' : ''}
        </p>
        {!isLive && findings.message && (
          <p className="text-yellow-400 text-sm mt-3 bg-yellow-900/20 border border-yellow-700/40 rounded-lg p-3">
            {findings.message}
          </p>
        )}
      </div>

      {/* Summary */}
      {findings.summary && (
        <div className="bg-navy-800 border border-navy-600 rounded-xl p-5">
          <h3 className="text-white font-medium text-sm mb-2">Summary</h3>
          <p className="text-slate-300 text-sm whitespace-pre-wrap">{findings.summary}</p>
        </div>
      )}

      {/* Agent outputs */}
      <AgentCard label="Cold Chain Risk Analyst" text={findings.risk_analyst} />
      <AgentCard label="Cold Chain Domain Expert" text={findings.domain_expert} />
      <AgentCard label="Recommendation Specialist" text={findings.recommendation_specialist} />

      {/* Potential product damage */}
      {findings.potential_product_damage && (
        <div className="bg-navy-800 border border-navy-600 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="w-4 h-4 text-orange-400" />
            <h3 className="text-white font-medium text-sm">Potential Product Damage</h3>
          </div>
          <p className="text-slate-300 text-sm whitespace-pre-wrap">{findings.potential_product_damage}</p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <BulletList title="Possible Causes" items={findings.possible_causes} icon={<SearchCheck className="w-4 h-4 text-cyan-400" />} />
        <BulletList title="Containment Measures" items={findings.containment_measures} icon={<ShieldCheck className="w-4 h-4 text-teal-400" />} />
      </div>

      {/* Suggested actions (not approved recommendations) */}
      {findings.suggested_actions && findings.suggested_actions.length > 0 && (
        <div className="bg-navy-800 border border-navy-600 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-1">
            <ListChecks className="w-4 h-4 text-teal-400" />
            <h3 className="text-white font-medium text-sm">Suggested Actions</h3>
          </div>
          <p className="text-slate-500 text-xs mb-3">
            AI suggestions for a human reviewer — not approved and not stored as database recommendations.
          </p>
          <div className="space-y-2">
            {findings.suggested_actions.map((a, i) => (
              <div key={i} className="flex items-start gap-3 py-2 border-b border-navy-600 last:border-0">
                <span className="text-teal-400 text-xs font-bold mt-0.5">P{a.priority}</span>
                <div>
                  <p className="text-white text-sm">{a.action}</p>
                  <p className="text-slate-400 text-xs mt-0.5">{a.justification}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}