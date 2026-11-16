import React, { useState, useEffect } from 'react';
import { UserCheck, Database, CheckCircle2, RefreshCw, Clock } from 'lucide-react';
import { api } from '../services/api';

export const AdminDashboard: React.FC = () => {
  const [health, setHealth] = useState<any>(null);
  const [responders, setResponders] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchAdminData = async () => {
    setLoading(true);
    try {
      const [hData, rData] = await Promise.all([
        api.getSystemHealth(),
        api.getResponderRoster()
      ]);
      setHealth(hData);
      setResponders(rData);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAdminData();
  }, []);

  const [verifying, setVerifying] = useState<number | null>(null);
  const handleVerify = async (userId: number) => {
    setVerifying(userId);
    try {
      await api.verifyResponder(userId);
      await fetchAdminData();
    } catch (err) {
      console.error(err);
    } finally {
      setVerifying(null);
    }
  };

  const db = health?.database;
  const vectors = db?.vector_search;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-900 text-teal-400 text-xs font-semibold mb-2">
            <UserCheck className="w-3.5 h-3.5" />
            Civic Operations & Administrative Oversight
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold text-slate-900">System Command & Diagnostics</h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Monitor real-time infrastructure, database adapters, and responder credentials.
          </p>
        </div>

        <button
          onClick={fetchAdminData}
          className="p-2 text-slate-500 hover:text-slate-800 rounded-xl hover:bg-slate-100 border border-slate-200 transition"
          title="Refresh Diagnostics"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Database & Infrastructure Diagnostics Card */}
      <div className="bg-slate-900 text-white rounded-3xl p-6 sm:p-8 border border-slate-800 shadow-xl space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-teal-600/30 border border-teal-500/40 p-2 flex items-center justify-center">
              <Database className="w-6 h-6 text-teal-400" />
            </div>
            <div>
              <h2 className="text-lg font-bold">Database Adapter Layer</h2>
              <span className="text-xs text-slate-400">Zero-cost development to IBM Db2 enterprise deployment</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400">Status:</span>
            <span className="inline-flex items-center gap-1.5 text-xs font-bold text-emerald-400 bg-emerald-500/20 px-3 py-1 rounded-full border border-emerald-500/30">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              {health?.status?.toUpperCase() || 'CHECKING'}
            </span>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
          <div className="bg-slate-800/80 p-4 rounded-xl border border-slate-700">
            <span className="text-slate-400 block text-[11px] uppercase font-bold">Configured Database Mode</span>
            <span className="text-base font-extrabold text-teal-400 mt-1 block uppercase">
              {db?.mode || '—'}
            </span>
            <span className="text-[11px] text-slate-300 mt-1 block">
              Driver: {db?.driver || '—'}
            </span>
            {db?.details?.server_version && (
              <span className="text-[11px] text-slate-300 mt-1 block">
                Server: {db.details.server_version} · schema {db.details.current_schema}
              </span>
            )}
          </div>

          <div className="bg-slate-800/80 p-4 rounded-xl border border-slate-700">
            <span className="text-slate-400 block text-[11px] uppercase font-bold">AI Intelligence Engine</span>
            <span className="text-base font-extrabold text-white mt-1 block">
              {vectors?.enabled ? 'Haystack BM25 + Db2 VECTOR' : 'Haystack BM25 + Triage Agents'}
            </span>
            <span className="text-[11px] text-slate-300 mt-1 block">
              {vectors?.enabled
                ? `Embeddings: ${vectors.model} (${vectors.dimensions} dims)`
                : 'Agents: Intake, Triage, Knowledge, Insights'}
            </span>
          </div>

          <div className="bg-slate-800/80 p-4 rounded-xl border border-slate-700">
            <span className="text-slate-400 block text-[11px] uppercase font-bold">Backend Framework</span>
            <span className="text-base font-extrabold text-white mt-1 block">
              Python 3.11 • FastAPI
            </span>
            <span className="text-[11px] text-slate-300 mt-1 block">
              Environment: {health?.environment || 'development'}
            </span>
          </div>
        </div>

        <div className="bg-slate-800/40 p-4 rounded-xl border border-slate-700/60 text-xs text-slate-300">
          <strong className="text-white block mb-1">IBM Db2 Integration Status:</strong>
          {db?.mode === 'db2' ? (
            <p className="text-teal-300">
              {db.connected
                ? `✓ Connected to IBM Db2 (${db.details?.database}) through ibm_db / ibm_db_sa. Server time ${db.details?.server_time}.`
                : `✗ Db2 connection failed: ${db.details?.error ?? 'unknown error'}`}
              {db.connected && (vectors?.enabled
                ? ' Semantic search runs inside Db2 with VECTOR_DISTANCE.'
                : ` Vector search inactive: ${vectors?.reason ?? 'not configured'}.`)}
            </p>
          ) : (
            <p className="text-slate-400">
              Application is currently running on the <strong>{health?.database?.mode?.toUpperCase() || 'SQLITE'}</strong> development adapter. 
              To switch to IBM Db2, set <code className="text-teal-300 bg-slate-900 px-1 py-0.5 rounded">DATABASE_MODE=db2</code> with your 
              DB2 host credentials in <code className="text-teal-300 bg-slate-900 px-1 py-0.5 rounded">backend/.env</code>.
            </p>
          )}
        </div>
      </div>

      {/* Verified Responders Roster */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-4">
        <h2 className="text-lg font-bold text-slate-900">Community Responders</h2>
        <p className="text-xs text-slate-500 -mt-2">Self-registered responders cannot act on incidents until an admin verifies them.</p>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {responders.map((r) => (
            <div key={r.id} className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 flex items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-bold text-slate-900 text-sm">{r.full_name}</h3>
                  <span className="text-[10px] font-mono bg-slate-200 text-slate-700 px-1.5 py-0.5 rounded font-bold">
                    {r.badge_number}
                  </span>
                </div>
                <span className="text-xs text-slate-500 capitalize">{r.service_type.replace('_', ' ')}</span>
                <div className="flex items-center gap-2 text-xs text-slate-400 mt-1">
                  <span>Rating: <strong className="text-slate-700">{r.rating} ★</strong></span>
                  <span>•</span>
                  <span className={r.is_available ? 'text-emerald-700 font-semibold' : 'text-slate-500'}>
                    {r.is_available ? 'Available' : 'Off-duty'}
                  </span>
                </div>
              </div>

              {r.is_verified_by_admin ? (
                <span className="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-800 bg-emerald-100 px-2.5 py-1 rounded-full">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  Verified
                </span>
              ) : (
                <button
                  onClick={() => handleVerify(r.user_id)}
                  disabled={verifying === r.user_id}
                  className="inline-flex items-center gap-1 text-[11px] font-bold text-amber-900 bg-amber-100 hover:bg-amber-200 px-2.5 py-1 rounded-full disabled:opacity-50"
                >
                  <Clock className="w-3.5 h-3.5" />
                  {verifying === r.user_id ? 'Verifying…' : 'Pending · Verify'}
                </button>
              )}
            </div>
          ))}
        </div>
      </div>

    </div>
  );
};
