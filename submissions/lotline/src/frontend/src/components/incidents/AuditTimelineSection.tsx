import React from 'react';
import { History, UserCheck, Bot, Clock, CheckCircle2, XCircle } from 'lucide-react';
import type { AuditRecord } from '../../services/api';

interface AuditTimelineSectionProps {
  auditLogs: AuditRecord[];
}

export const AuditTimelineSection: React.FC<AuditTimelineSectionProps> = ({ auditLogs }) => {
  return (
    <section id="audit-log" className="bento-opaque-card p-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-white/8">
        <div>
          <div className="flex items-center gap-2">
            <History className="w-4 h-4 text-[#23cad2]" />
            <h2 className="text-sm font-mono font-bold uppercase tracking-wider text-white">
              IMMUTABLE AUDIT TIMELINE
            </h2>
          </div>
          <p className="text-xs text-white/50 mt-1">
            Tamper-evident record of all AI inferences, system alerts and human operator decisions from Db2
          </p>
        </div>
        <span className="font-mono text-[10px] text-white/50 bg-white/5 px-2.5 py-1 rounded border border-white/10 self-start sm:self-auto">
          TABLE: LOTLINE_APP.AUDIT_LOG
        </span>
      </div>

      {/* Timeline Stream */}
      <div className="mt-6 space-y-4 relative pl-6 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-[1px] before:bg-white/10">
        {auditLogs.map((log) => {
          const isHuman =
            log.actor.toLowerCase().includes('operator') ||
            log.actor.toLowerCase().includes('user') ||
            log.actor.toLowerCase().includes('officer') ||
            log.actor.toLowerCase().includes('assurance');
          const isApproval = log.event_type.includes('APPROVED');
          const isRejection = log.event_type.includes('REJECTED');

          return (
            <div key={log.audit_id} className="relative flex flex-col sm:flex-row sm:items-start justify-between gap-2 text-xs">
              {/* Timeline Indicator Dot */}
              <span
                className={`absolute -left-6 top-1 w-3 h-3 rounded-full border-2 border-[#171717] flex items-center justify-center ${
                  isApproval
                    ? 'bg-emerald-400'
                    : isRejection
                    ? 'bg-red-400'
                    : isHuman
                    ? 'bg-[#23cad2]'
                    : 'bg-[#1680ac]'
                }`}
              />

              <div className="flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span
                    className={`font-mono font-bold tracking-wide ${
                      isApproval ? 'text-emerald-300' : isRejection ? 'text-red-300' : 'text-white'
                    }`}
                  >
                    {log.event_type}
                  </span>
                  <span className="text-[10px] font-mono text-white/40">
                    ID: {log.audit_id}
                  </span>
                  <span
                    className={`inline-flex items-center gap-1 text-[10px] font-mono px-2 py-0.2 rounded ${
                      isHuman
                        ? 'bg-purple-500/15 text-purple-300 border border-purple-500/20'
                        : 'bg-[#23cad2]/15 text-[#8ef5e6] border border-[#23cad2]/30'
                    }`}
                  >
                    {isHuman ? <UserCheck className="w-2.5 h-2.5" /> : <Bot className="w-2.5 h-2.5" />}
                    {log.actor}
                  </span>
                </div>

                <p className="text-xs text-white/75 mt-1 font-normal leading-relaxed">
                  {log.details || 'System event recorded in Db2 log.'}
                </p>
              </div>

              {/* Timestamp */}
              <div className="text-[10px] font-mono text-white/40 shrink-0 flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {log.created_at ? new Date(log.created_at).toLocaleString() : 'Recent'}
              </div>
            </div>
          );
        })}

        {auditLogs.length === 0 && (
          <div className="text-center py-6 text-white/40 font-mono text-xs">
            No audit records found.
          </div>
        )}
      </div>
    </section>
  );
};
