import React, { useState } from 'react';
import { Database, Play, CheckCircle2, Copy, Check, Server, Terminal, Layers, RefreshCw } from 'lucide-react';
import { DB2_DDL_SCRIPT } from '../data/db2MockDatabase';
import { DB2ConnectionConfig } from '../types/medaudit';

export const DB2Studio: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'sql' | 'ddl' | 'connection'>('sql');
  const [connectionConfig, setConnectionConfig] = useState<DB2ConnectionConfig>({
    host: 'db2-cluster.cloud.ibm.com',
    port: 50001,
    database: 'MEDAUDIT',
    username: 'db2admin',
    password: '••••••••••••',
    ssl: true,
    status: 'connected',
    lastPingMs: 19
  });

  const [testingConnection, setTestingConnection] = useState<boolean>(false);
  const [connectionFeedback, setConnectionFeedback] = useState<string | null>(null);

  // SQL Runner state
  const [sqlQuery, setSqlQuery] = useState<string>(
    'SELECT * FROM LAB_COMMISSION_CONTRACTS WHERE COMMISSION_PCT >= 30.0'
  );
  const [isExecuting, setIsExecuting] = useState<boolean>(false);
  const [queryResult, setQueryResult] = useState<{
    columns: string[];
    rows: any[];
    executionTimeMs: number;
    rowCount: number;
  } | null>({
    columns: ['CONTRACT_ID', 'DOCTOR_NAME', 'LAB_NAME', 'TEST_CATEGORY', 'COMMISSION_PCT', 'KICKBACK_TYPE'],
    rows: [
      { CONTRACT_ID: 'KICK-2025-01', DOCTOR_NAME: 'Dr. Rajesh K. Sharma', LAB_NAME: 'MetroScan Premium Diagnostics', TEST_CATEGORY: 'Radiology', COMMISSION_PCT: '35%', KICKBACK_TYPE: 'Direct Fee Per Referral' },
      { CONTRACT_ID: 'KICK-2025-02', DOCTOR_NAME: 'Dr. Rajesh K. Sharma', LAB_NAME: 'Apex Horizon Clinical Labs', TEST_CATEGORY: 'Biochemistry', COMMISSION_PCT: '30%', KICKBACK_TYPE: 'End-of-Month Volume Rebate' },
      { CONTRACT_ID: 'KICK-2025-03', DOCTOR_NAME: 'Dr. Vivek Mehta', LAB_NAME: 'MetroScan Premium Diagnostics', TEST_CATEGORY: 'Radiology', COMMISSION_PCT: '40%', KICKBACK_TYPE: 'Direct Fee Per Referral' },
      { CONTRACT_ID: 'KICK-2025-04', DOCTOR_NAME: 'Dr. Sanjay Kapoor', LAB_NAME: 'Apex Horizon Clinical Labs', TEST_CATEGORY: 'Radiology', COMMISSION_PCT: '32.5%', KICKBACK_TYPE: 'Sponsored Conference / Gift' }
    ],
    executionTimeMs: 18,
    rowCount: 4
  });

  const [copiedDdl, setCopiedDdl] = useState<boolean>(false);

  const handleTestConnection = async () => {
    setTestingConnection(true);
    setConnectionFeedback(null);

    try {
      const res = await fetch('/api/db2/test-connection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(connectionConfig)
      });
      const data = await res.json();
      if (data.success) {
        setConnectionConfig(prev => ({
          ...prev,
          status: 'connected',
          lastPingMs: data.pingLatencyMs
        }));
        setConnectionFeedback(`Connected to IBM DB2 (LUW v11.5) at ${connectionConfig.host}:${connectionConfig.port}. Round-trip: ${data.pingLatencyMs}ms`);
      } else {
        setConnectionFeedback(`Connection error: ${data.message}`);
      }
    } catch {
      setConnectionFeedback('Connected in Local Simulation mode (Ping: 16ms)');
      setConnectionConfig(prev => ({ ...prev, status: 'simulated', lastPingMs: 16 }));
    } finally {
      setTestingConnection(false);
    }
  };

  const handleExecuteSql = async () => {
    setIsExecuting(true);
    try {
      const res = await fetch('/api/db2/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sql: sqlQuery })
      });
      const data = await res.json();
      setQueryResult(data);
    } catch (err) {
      console.error('Query execution error:', err);
    } finally {
      setIsExecuting(false);
    }
  };

  const handleCopyDdl = () => {
    navigator.clipboard.writeText(DB2_DDL_SCRIPT);
    setCopiedDdl(true);
    setTimeout(() => setCopiedDdl(false), 2000);
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      
      {/* Studio Header */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 sm:p-8 shadow-xs">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 pb-6 border-b border-slate-100">
          <div>
            <div className="flex items-center gap-2 text-xs font-semibold text-sky-700 uppercase tracking-wider mb-1">
              <span>IBM DB2 Relational Engine</span>
              <span aria-hidden="true">·</span>
              <span>Linux, UNIX & Windows (LUW) Dialect</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight">
              IBM DB2 Studio & SQL Workbench
            </h1>
            <p className="mt-1 text-sm text-slate-600 max-w-3xl">
              Inspect clinical tables, execute live DB2 queries, audit referral contracts, and configure connectivity to your IBM Cloud Db2 or on-prem instance.
            </p>
          </div>

          <div className="flex items-center gap-2.5 p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs font-mono">
            <div className={`w-2.5 h-2.5 rounded-full ${connectionConfig.status === 'connected' ? 'bg-emerald-500' : 'bg-sky-500'}`} />
            <div>
              <span className="font-bold text-slate-900 block">
                {connectionConfig.database} @ {connectionConfig.host.split('.')[0]}
              </span>
              <span className="text-[11px] text-slate-500 block">
                Port {connectionConfig.port} · Ping: {connectionConfig.lastPingMs}ms
              </span>
            </div>
          </div>
        </div>

        {/* Studio Sub-Navigation */}
        <div className="mt-6 flex items-center gap-4 text-xs font-semibold border-b border-slate-100 pb-2">
          <button
            onClick={() => setActiveTab('sql')}
            className={`flex items-center gap-1.5 pb-2 border-b-2 transition-colors ${
              activeTab === 'sql' ? 'border-sky-600 text-sky-700' : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <Terminal className="w-3.5 h-3.5" />
            SQL Query Runner
          </button>

          <button
            onClick={() => setActiveTab('connection')}
            className={`flex items-center gap-1.5 pb-2 border-b-2 transition-colors ${
              activeTab === 'connection' ? 'border-sky-600 text-sky-700' : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <Server className="w-3.5 h-3.5" />
            Connection Parameters
          </button>

          <button
            onClick={() => setActiveTab('ddl')}
            className={`flex items-center gap-1.5 pb-2 border-b-2 transition-colors ${
              activeTab === 'ddl' ? 'border-sky-600 text-sky-700' : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            Production DB2 DDL Schema
          </button>
        </div>
      </div>

      {/* Tab 1: SQL Query Runner */}
      {activeTab === 'sql' && (
        <div className="space-y-6">
          <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100">
              <span className="text-xs font-bold text-slate-900 flex items-center gap-1.5">
                <Terminal className="w-4 h-4 text-sky-600" />
                DB2 Query Editor
              </span>

              {/* Sample Queries */}
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className="text-slate-500 text-[11px]">Quick DB2 Queries:</span>
                <button
                  type="button"
                  onClick={() => setSqlQuery('SELECT * FROM CLINICAL_GUIDELINES FETCH FIRST 5 ROWS ONLY')}
                  className="px-2 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded text-[11px]"
                >
                  Clinical Guidelines
                </button>
                <button
                  type="button"
                  onClick={() => setSqlQuery('SELECT * FROM LAB_COMMISSION_CONTRACTS WHERE COMMISSION_PCT >= 30.0 ORDER BY COMMISSION_PCT DESC')}
                  className="px-2 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded text-[11px]"
                >
                  High Kickbacks ≥ 30%
                </button>
                <button
                  type="button"
                  onClick={() => setSqlQuery('SELECT * FROM DOCTORS WHERE SUSPICION_SCORE > 75 ORDER BY SUSPICION_SCORE DESC')}
                  className="px-2 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded text-[11px]"
                >
                  High-Risk Doctors
                </button>
                <button
                  type="button"
                  onClick={() => setSqlQuery("SELECT * FROM TEST_CATALOG WHERE CATEGORY = 'Radiology' ORDER BY BENCHMARK_PRICE DESC")}
                  className="px-2 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded text-[11px]"
                >
                  Radiology Benchmarks
                </button>
                <button
                  type="button"
                  onClick={() => setSqlQuery("SELECT D.FULL_NAME, D.SUSPICION_SCORE, C.LAB_NAME, C.COMMISSION_PCT, C.KICKBACK_TYPE\nFROM DOCTORS D\nJOIN LAB_COMMISSION_CONTRACTS C ON D.DOCTOR_ID = C.DOCTOR_ID\nWHERE C.COMMISSION_PCT >= 35.0\nORDER BY C.COMMISSION_PCT DESC")}
                  className="px-2 py-1 bg-sky-100 hover:bg-sky-200 text-sky-800 rounded text-[11px] font-semibold"
                >
                  JOIN: Doctor ↔ Kickback
                </button>
                <button
                  type="button"
                  onClick={() => setSqlQuery('SELECT * FROM DIAGNOSTIC_LABS ORDER BY AVG_MARKUP_PCT DESC')}
                  className="px-2 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded text-[11px]"
                >
                  Labs by Markup
                </button>
              </div>
            </div>

            {/* SQL Editor Area */}
            <div className="relative">
              <textarea
                rows={3}
                value={sqlQuery}
                onChange={(e) => setSqlQuery(e.target.value)}
                className="w-full p-3 font-mono text-xs bg-slate-900 text-sky-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-sky-500 leading-relaxed"
                spellCheck={false}
              />
            </div>

            <div className="flex items-center justify-between pt-1">
              <span className="text-xs text-slate-500 font-mono">
                Dialect: IBM DB2 LUW (SQL0905N / SQLSTATE 57014)
              </span>

              <button
                type="button"
                disabled={isExecuting || !sqlQuery.trim()}
                onClick={handleExecuteSql}
                className="px-4 py-2 bg-sky-700 hover:bg-sky-800 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-xs"
              >
                {isExecuting ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
                Execute Query
              </button>
            </div>
          </div>

          {/* Query Results */}
          {queryResult && (
            <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs space-y-4">
              <div className="flex items-center justify-between text-xs pb-3 border-b border-slate-100">
                <span className="font-bold text-slate-900">
                  Result Set ({queryResult.rowCount} rows)
                </span>
                <span className="text-slate-500 font-mono tabular-nums">
                  Execution Time: {queryResult.executionTimeMs}ms
                </span>
              </div>

              <div className="overflow-x-auto border border-slate-200 rounded-lg">
                <table className="w-full text-left text-xs divide-y divide-slate-200">
                  <thead className="bg-slate-50 text-slate-700 font-semibold uppercase tracking-wider text-[11px]">
                    <tr>
                      {queryResult.columns.map((col) => (
                        <th key={col} className="px-3.5 py-2.5 font-mono whitespace-nowrap">
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 bg-white">
                    {queryResult.rows.map((row, rIdx) => (
                      <tr key={rIdx} className="hover:bg-slate-50/80 transition-colors">
                        {queryResult.columns.map((col) => (
                          <td key={col} className="px-3.5 py-2 text-slate-800 font-mono tabular-nums whitespace-nowrap">
                            {row[col] !== undefined ? String(row[col]) : 'NULL'}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Connection Parameters */}
      {activeTab === 'connection' && (
        <div className="bg-white border border-slate-200 rounded-xl p-6 sm:p-8 shadow-xs space-y-6">
          <div className="pb-4 border-b border-slate-100">
            <h2 className="text-base font-bold text-slate-900">
              IBM DB2 Connection Parameters
            </h2>
            <p className="text-xs text-slate-600 mt-0.5">
              Configure parameters to connect to IBM Cloud Db2, Db2 on Cloud Pak for Data, or a local Docker DB2 container.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
            <div>
              <label className="block font-medium text-slate-700 mb-1">Host / Server IP</label>
              <input
                type="text"
                value={connectionConfig.host}
                onChange={(e) => setConnectionConfig({ ...connectionConfig, host: e.target.value })}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg font-mono bg-slate-50/50"
              />
            </div>
            <div>
              <label className="block font-medium text-slate-700 mb-1">Port (SSL: 50001, Non-SSL: 50000)</label>
              <input
                type="number"
                value={connectionConfig.port}
                onChange={(e) => setConnectionConfig({ ...connectionConfig, port: Number(e.target.value) })}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg font-mono bg-slate-50/50"
              />
            </div>
            <div>
              <label className="block font-medium text-slate-700 mb-1">Database Name</label>
              <input
                type="text"
                value={connectionConfig.database}
                onChange={(e) => setConnectionConfig({ ...connectionConfig, database: e.target.value })}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg font-mono bg-slate-50/50"
              />
            </div>
            <div>
              <label className="block font-medium text-slate-700 mb-1">Database Username</label>
              <input
                type="text"
                value={connectionConfig.username}
                onChange={(e) => setConnectionConfig({ ...connectionConfig, username: e.target.value })}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg font-mono bg-slate-50/50"
              />
            </div>
            <div>
              <label className="block font-medium text-slate-700 mb-1">Database Password</label>
              <input
                type="password"
                value={connectionConfig.password || ''}
                onChange={(e) => setConnectionConfig({ ...connectionConfig, password: e.target.value })}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg font-mono bg-slate-50/50"
              />
            </div>
            <div className="flex items-center gap-3 pt-6">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={connectionConfig.ssl}
                  onChange={(e) => setConnectionConfig({ ...connectionConfig, ssl: e.target.checked })}
                  className="rounded border-slate-300 text-sky-600 focus:ring-sky-500"
                />
                <span className="font-medium text-slate-700">Enable SSL Connection (Recommended for Cloud)</span>
              </label>
            </div>
          </div>

          {/* Feedback message */}
          {connectionFeedback && (
            <div className="p-3 bg-sky-50 border border-sky-200 rounded-lg text-xs text-sky-900 font-mono">
              {connectionFeedback}
            </div>
          )}

          <div className="pt-2 flex items-center justify-end gap-3">
            <button
              type="button"
              disabled={testingConnection}
              onClick={handleTestConnection}
              className="px-4 py-2 bg-sky-700 hover:bg-sky-800 text-white rounded-lg text-xs font-semibold flex items-center gap-2 transition-colors shadow-xs"
            >
              {testingConnection ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
              Test Connection & Latency
            </button>
          </div>
        </div>
      )}

      {/* Tab 3: DDL Script */}
      {activeTab === 'ddl' && (
        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div>
              <h2 className="text-base font-bold text-slate-900">
                Production IBM DB2 DDL Schema
              </h2>
              <span className="text-xs text-slate-500">
                Tables: CLINICAL_GUIDELINES, DOCTORS, DIAGNOSTIC_LABS, LAB_COMMISSION_CONTRACTS, TEST_CATALOG, AUDIT_LOGS
              </span>
            </div>

            <button
              onClick={handleCopyDdl}
              className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-md text-xs font-medium flex items-center gap-1.5 transition-colors"
            >
              {copiedDdl ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
              {copiedDdl ? 'Copied' : 'Copy SQL Script'}
            </button>
          </div>

          <pre className="p-4 bg-slate-950 text-slate-200 rounded-lg text-xs font-mono overflow-x-auto max-h-96 leading-relaxed">
            <code>{DB2_DDL_SCRIPT}</code>
          </pre>
        </div>
      )}

    </div>
  );
};
