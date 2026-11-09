import React, { useEffect, useState } from 'react';
import { Settings as SettingsIcon, Database, Cpu, Shield, RefreshCw, Terminal, CheckCircle2, AlertTriangle } from 'lucide-react';
import { apiClient } from '../api/client';

export default function Settings({ dbHealth }) {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchHealth = async () => {
    setLoading(true);
    try {
      const res = await apiClient.getHealth();
      setHealth(res.data);
    } catch (err) {
      console.error('Failed to get health:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
  }, []);

  return (
    <div className="max-w-4xl space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-[#E0E0E0]">
        <div className="flex items-center space-x-2">
          <div className="p-1.5 bg-[#EDF5FF] text-[#0F62FE] rounded">
            <SettingsIcon className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-[#161616]">System & Database Settings</h1>
            <p className="text-xs text-[#525252]">
              ClaimGuard AI runtime configuration and IBM Db2 connection parameters
            </p>
          </div>
        </div>

        <button
          onClick={fetchHealth}
          className="flex items-center space-x-1.5 px-3 py-1.5 text-xs bg-white border border-[#E0E0E0] hover:bg-gray-50 text-[#161616] rounded-sm transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh Probes</span>
        </button>
      </div>

      {/* Database Configuration Card */}
      <div className="bg-white border border-[#E0E0E0] p-5 rounded-sm shadow-sm space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-gray-100">
          <div className="flex items-center space-x-2">
            <Database className="w-4 h-4 text-[#0F62FE]" />
            <h2 className="text-xs font-bold uppercase tracking-wider font-mono text-[#161616]">
              IBM Db2 Enterprise Relational Connection
            </h2>
          </div>
          <span
            className={`px-2 py-0.5 rounded text-[11px] font-semibold ${
              health?.database?.connected
                ? 'bg-emerald-100 text-emerald-800'
                : 'bg-amber-100 text-amber-800'
            }`}
          >
            {health?.database?.connected ? 'ONLINE' : 'DISCONNECTED (DEMO MODE)'}
          </span>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs font-mono">
          <div>
            <span className="text-gray-400 block text-[10px] uppercase">Database Host</span>
            <span className="font-semibold text-gray-900">{health?.database?.host || 'localhost'}</span>
          </div>
          <div>
            <span className="text-gray-400 block text-[10px] uppercase">Port</span>
            <span className="font-semibold text-gray-900">{health?.database?.port || 50000}</span>
          </div>
          <div>
            <span className="text-gray-400 block text-[10px] uppercase">Database Name</span>
            <span className="font-semibold text-gray-900">{health?.database?.database_name || 'testdb'}</span>
          </div>
          <div>
            <span className="text-gray-400 block text-[10px] uppercase">Python Driver</span>
            <span className="font-semibold text-[#0F62FE]">{health?.database?.driver || 'ibm_db 3.3.0'}</span>
          </div>
        </div>

        {!health?.database?.connected && (
          <div className="mt-4 p-4 bg-amber-50 border border-amber-200 rounded text-xs space-y-2">
            <div className="flex items-center space-x-1.5 font-semibold text-amber-900">
              <AlertTriangle className="w-4 h-4" />
              <span>IBM Db2 Container Not Detected Locally</span>
            </div>
            <p className="text-amber-800 leading-relaxed">
              The application is currently executing with in-memory parity seeded from <code className="bg-white px-1">schema.sql</code>. To connect a live IBM Db2 Community Edition container, launch:
            </p>
            <pre className="p-3 bg-white border border-amber-200 rounded font-mono text-[11px] text-gray-800 overflow-x-auto">
{`docker run -d --name db2server \\
  --restart always \\
  -p 50000:50000 \\
  --env LICENSE=accept \\
  --env DB2INSTANCE=db2inst1 \\
  --env DB2INST1_PASSWORD=YourSecurePassword123! \\
  --env DBNAME=testdb \\
  -v db2_data:/database \\
  icr.io/db2_community/db2:latest`}
            </pre>
            <p className="text-amber-800">
              Then run <code className="bg-white px-1 font-mono">python src/backend/database/init_db.py</code> to execute the DDL migrations.
            </p>
          </div>
        )}
      </div>

      {/* AI & Framework Config Card */}
      <div className="bg-white border border-[#E0E0E0] p-5 rounded-sm shadow-sm space-y-4">
        <div className="flex items-center space-x-2 pb-3 border-b border-gray-100 text-[#8A3FFC]">
          <Cpu className="w-4 h-4" />
          <h2 className="text-xs font-bold uppercase tracking-wider font-mono text-[#161616]">
            LangChain & Google Gemini 2.5 Intelligence
          </h2>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-xs font-mono">
          <div>
            <span className="text-gray-400 block text-[10px] uppercase">Primary AI Framework</span>
            <span className="font-semibold text-gray-900">LangChain 1.4.9</span>
          </div>
          <div>
            <span className="text-gray-400 block text-[10px] uppercase">Orchestration Engine</span>
            <span className="font-semibold text-gray-900">LangGraph 1.2.20</span>
          </div>
          <div>
            <span className="text-gray-400 block text-[10px] uppercase">Document Model</span>
            <span className="font-semibold text-gray-900">gemini-2.5-flash</span>
          </div>
        </div>
      </div>

      {/* Participant Metadata */}
      <div className="bg-white border border-[#E0E0E0] p-5 rounded-sm shadow-sm">
        <h2 className="text-xs font-bold uppercase tracking-wider font-mono text-[#161616] pb-3 border-b border-gray-100">
          Hackathon Project Submission Information
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-3 text-xs font-mono">
          <div>
            <span className="text-gray-400 block text-[10px] uppercase">Participant</span>
            <span className="font-semibold text-gray-900">Nitesh Barnwal</span>
          </div>
          <div>
            <span className="text-gray-400 block text-[10px] uppercase">GitHub Handle</span>
            <span className="font-semibold text-[#0F62FE]">@Nitesh0517</span>
          </div>
          <div>
            <span className="text-gray-400 block text-[10px] uppercase">Hackathon</span>
            <span className="font-semibold text-gray-900">IBM Db2Hack 2026</span>
          </div>
          <div>
            <span className="text-gray-400 block text-[10px] uppercase">Category</span>
            <span className="font-semibold text-gray-900">Individual Participant</span>
          </div>
        </div>
      </div>
    </div>
  );
}
