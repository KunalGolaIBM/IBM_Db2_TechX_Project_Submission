import React, { useState } from 'react';
import { Database, AlertTriangle, CheckCircle, Info, X } from 'lucide-react';

export default function Db2StatusBadge({ dbHealth }) {
  const [showModal, setShowModal] = useState(false);
  const isConnected = dbHealth?.connected;

  return (
    <>
      <button
        onClick={() => setShowModal(true)}
        className={`flex items-center space-x-2 px-3 py-1 text-xs font-medium border rounded transition-colors ${
          isConnected
            ? 'bg-emerald-50 text-emerald-700 border-emerald-300 hover:bg-emerald-100'
            : 'bg-amber-50 text-amber-800 border-amber-300 hover:bg-amber-100'
        }`}
        title="Click to view IBM Db2 connection details"
      >
        <Database className="w-3.5 h-3.5" />
        <span>
          {isConnected ? 'IBM Db2: Online' : 'Db2: Disconnected (Demo Data)'}
        </span>
        {isConnected ? (
          <CheckCircle className="w-3 h-3 text-emerald-600" />
        ) : (
          <AlertTriangle className="w-3 h-3 text-amber-600" />
        )}
      </button>

      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white border border-[#E0E0E0] shadow-xl rounded-sm max-w-lg w-full p-6 text-left">
            <div className="flex items-center justify-between pb-3 border-b border-[#E0E0E0]">
              <div className="flex items-center space-x-2">
                <Database className="w-5 h-5 text-[#0F62FE]" />
                <h3 className="font-semibold text-base text-[#161616]">IBM Db2 Connection Details</h3>
              </div>
              <button
                onClick={() => setShowModal(false)}
                className="text-gray-400 hover:text-gray-600 p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="mt-4 space-y-3 text-xs text-[#525252]">
              <div className="flex justify-between py-1 border-b border-gray-100">
                <span className="font-medium text-gray-700">Database Driver:</span>
                <span className="font-mono text-gray-900">{dbHealth?.driver || 'ibm_db 3.3.0'}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-gray-100">
                <span className="font-medium text-gray-700">Connection Status:</span>
                <span className={`font-semibold ${isConnected ? 'text-emerald-700' : 'text-amber-700'}`}>
                  {isConnected ? 'ACTIVE LIVE CONNECTION' : 'DISCONNECTED (DEMO MODE)'}
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-gray-100">
                <span className="font-medium text-gray-700">Target Host / Port:</span>
                <span className="font-mono">{dbHealth?.host || 'localhost'}:{dbHealth?.port || 50000}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-gray-100">
                <span className="font-medium text-gray-700">Database Name:</span>
                <span className="font-mono">{dbHealth?.database_name || 'testdb'}</span>
              </div>

              {!isConnected && (
                <div className="mt-4 p-3 bg-amber-50 border border-amber-200 rounded text-xs space-y-2">
                  <div className="flex items-center space-x-1 font-semibold text-amber-900">
                    <Info className="w-4 h-4" />
                    <span>How to connect your real IBM Db2 instance</span>
                  </div>
                  <p className="text-amber-800">
                    Launch the official IBM Db2 Community Edition container:
                  </p>
                  <pre className="p-2 bg-white border border-amber-200 rounded font-mono text-[11px] text-gray-800 overflow-x-auto">
{`docker run -d --name db2server \\
  -p 50000:50000 \\
  --env LICENSE=accept \\
  --env DB2INSTANCE=db2inst1 \\
  --env DB2INST1_PASSWORD=YourPassword123! \\
  --env DBNAME=testdb \\
  icr.io/db2_community/db2:latest`}
                  </pre>
                  <p className="text-amber-700">
                    Once running, set <code className="bg-white px-1">DB2_PASSWORD</code> in <code className="bg-white px-1">.env</code> and restart the backend.
                  </p>
                </div>
              )}
            </div>

            <div className="mt-5 flex justify-end">
              <button
                onClick={() => setShowModal(false)}
                className="px-4 py-1.5 bg-[#0F62FE] text-white text-xs font-medium hover:bg-[#0353E9] transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
