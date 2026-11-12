import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Activity, CheckCircle2, MapPin, RefreshCw, Power, Pill } from 'lucide-react';
import { api } from '../services/api';
import { Incident, AssistanceRequest } from '../types';
import { useAuth } from '../context/AuthContext';

export const ResponderDashboard: React.FC = () => {
  const { user } = useAuth();
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [requests, setRequests] = useState<AssistanceRequest[]>([]);
  const [isAvailable, setIsAvailable] = useState<boolean>(true);
  const [loading, setLoading] = useState<boolean>(true);
  const [actionInProgress, setActionInProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchAssignments = async () => {
    setLoading(true);
    try {
      const data = await api.getResponderAssignments();
      setError(null);
      setIncidents(data.incidents || []);
      setRequests(data.assistance_requests || []);
      setIsAvailable(data.is_available);
    } catch (err: any) {
      setError(err.message || 'Could not load assignments.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAssignments();
  }, []);

  const handleToggleAvailability = async () => {
    try {
      const updated = !isAvailable;
      setIsAvailable(updated);
      await api.updateAvailability(updated);
    } catch (err: any) {
      alert("Error updating availability: " + err.message);
      setIsAvailable(!isAvailable);
    }
  };

  const handleAcknowledge = async (incidentId: number) => {
    setActionInProgress(incidentId);
    try {
      await api.acknowledgeIncident(incidentId);
      await fetchAssignments();
    } catch (err: any) {
      alert("Error: " + err.message);
    } finally {
      setActionInProgress(null);
    }
  };

  const handleAdvanceStatus = async (incidentId: number, nextStatus: string) => {
    setActionInProgress(incidentId);
    try {
      await api.updateIncidentStatus(incidentId, nextStatus, `Status updated to ${nextStatus.replace('_', ' ')} by responder.`);
      await fetchAssignments();
    } catch (err: any) {
      alert("Error: " + err.message);
    } finally {
      setActionInProgress(null);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      
      {/* Top Status Bar */}
      <div className="bg-slate-900 text-white rounded-3xl p-6 sm:p-8 border border-slate-800 shadow-xl flex flex-col md:flex-row items-center justify-between gap-6">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-teal-500/20 text-teal-300 text-xs font-semibold mb-2 border border-teal-500/30">
            <Activity className="w-3.5 h-3.5" />
            Verified Responder Command Center
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
            Officer {user?.full_name}
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Assigned Corridor: Sector 4 Civic Jurisdiction • Ready for Tactical & Medical Deployment
          </p>
        </div>

        {/* Availability Toggle */}
        <div className="flex items-center gap-4 bg-slate-800/80 p-3 rounded-2xl border border-slate-700">
          <div>
            <span className="text-[11px] text-slate-400 block font-medium">Duty Status</span>
            <span className={`text-sm font-bold flex items-center gap-1.5 ${isAvailable ? 'text-emerald-400' : 'text-slate-400'}`}>
              <span className={`w-2 h-2 rounded-full ${isAvailable ? 'bg-emerald-400 animate-ping' : 'bg-slate-500'}`} />
              {isAvailable ? 'ON-DUTY AVAILABLE' : 'OFF-DUTY'}
            </span>
          </div>

          <button
            onClick={handleToggleAvailability}
            className={`p-3 rounded-xl transition ${isAvailable ? 'bg-emerald-600 hover:bg-emerald-500 text-white' : 'bg-slate-700 hover:bg-slate-600 text-slate-300'}`}
            title="Toggle Availability"
          >
            <Power className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Active Incident Queue (2 Cols) */}
        <div className="lg:col-span-2 space-y-4">
          {error && (
            <div className="bg-amber-50 border border-amber-200 text-amber-900 text-sm rounded-xl px-4 py-3">
              {error}
            </div>
          )}
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold text-slate-900">Assigned Incident Queue</h2>
              <p className="text-xs text-slate-500">Live community distress reports awaiting response</p>
            </div>
            <button
              onClick={fetchAssignments}
              className="p-2 text-slate-500 hover:text-slate-800 rounded-lg hover:bg-slate-100 transition"
              title="Refresh"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>

          {incidents.length === 0 ? (
            <div className="bg-white rounded-2xl p-10 border border-slate-200 text-center space-y-3">
              <CheckCircle2 className="w-12 h-12 text-teal-600 mx-auto" />
              <h3 className="text-base font-semibold text-slate-800">Dispatch Queue Clear</h3>
              <p className="text-xs text-slate-500 max-w-sm mx-auto">
                No open emergency incidents in your sector. Stay on-duty for automated incoming alerts.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {incidents.map((inc) => (
                <div 
                  key={inc.id}
                  className={`bg-white rounded-2xl p-5 border shadow-sm space-y-4 transition ${
                    inc.priority === 'P1_CRITICAL' ? 'border-red-300 ring-2 ring-red-100' : 'border-slate-200'
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-bold text-slate-500">{inc.reference_code}</span>
                        <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full ${
                          inc.priority === 'P1_CRITICAL' ? 'bg-red-100 text-red-700 animate-pulse' :
                          inc.priority === 'P2_HIGH' ? 'bg-amber-100 text-amber-700' :
                          'bg-slate-100 text-slate-700'
                        }`}>
                          {inc.priority}
                        </span>
                        <span className="text-xs text-slate-400 capitalize">• {inc.incident_type.replace('_', ' ')}</span>
                      </div>
                      <h3 className="font-bold text-slate-900 text-lg mt-1">{inc.title}</h3>
                      <p className="text-xs text-slate-600 mt-1 leading-relaxed">{inc.description}</p>
                    </div>

                    <span className={`text-xs font-bold px-3 py-1 rounded-xl capitalize ${
                      inc.status === 'resolved' ? 'bg-emerald-100 text-emerald-800' :
                      inc.status === 'on_scene' ? 'bg-blue-100 text-blue-800' :
                      inc.status === 'acknowledged' ? 'bg-amber-100 text-amber-800' :
                      'bg-red-100 text-red-800'
                    }`}>
                      {inc.status.replace('_', ' ')}
                    </span>
                  </div>

                  <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-slate-100 text-xs">
                    <span className="text-slate-500 flex items-center gap-1 font-medium">
                      <MapPin className="w-3.5 h-3.5 text-slate-400" />
                      {inc.location_address || 'Designated Area'}
                    </span>

                    {/* Operational Action Buttons */}
                    <div className="flex items-center gap-2">
                      {inc.status === 'reported' && (
                        <button
                          onClick={() => handleAcknowledge(inc.id)}
                          disabled={actionInProgress === inc.id}
                          className="bg-teal-600 hover:bg-teal-500 text-white font-bold px-3.5 py-1.5 rounded-xl shadow-sm transition text-xs flex items-center gap-1"
                        >
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          Claim & Acknowledge
                        </button>
                      )}

                      {inc.status === 'acknowledged' && (
                        <button
                          onClick={() => handleAdvanceStatus(inc.id, 'responder_en_route')}
                          disabled={actionInProgress === inc.id}
                          className="bg-blue-600 hover:bg-blue-500 text-white font-bold px-3.5 py-1.5 rounded-xl shadow-sm transition text-xs"
                        >
                          Mark En Route
                        </button>
                      )}

                      {inc.status === 'responder_en_route' && (
                        <button
                          onClick={() => handleAdvanceStatus(inc.id, 'on_scene')}
                          disabled={actionInProgress === inc.id}
                          className="bg-purple-600 hover:bg-purple-500 text-white font-bold px-3.5 py-1.5 rounded-xl shadow-sm transition text-xs"
                        >
                          Log On-Scene Arrival
                        </button>
                      )}

                      {inc.status === 'on_scene' && (
                        <button
                          onClick={() => handleAdvanceStatus(inc.id, 'resolved')}
                          disabled={actionInProgress === inc.id}
                          className="bg-emerald-600 hover:bg-emerald-500 text-white font-bold px-3.5 py-1.5 rounded-xl shadow-sm transition text-xs"
                        >
                          Resolve & Close
                        </button>
                      )}

                      <Link
                        to={`/incidents/${inc.id}`}
                        className="text-slate-700 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 px-3 py-1.5 rounded-xl font-semibold transition"
                      >
                        Detail & Notes
                      </Link>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right Column: Assistance Queue & Protocols */}
        <div className="space-y-6">
          
          <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm space-y-4">
            <h3 className="font-bold text-slate-900 text-sm flex items-center gap-2">
              <Pill className="w-4 h-4 text-teal-600" />
              Community Welfare Requests
            </h3>

            {requests.length === 0 ? (
              <p className="text-xs text-slate-500 italic">No pending elder assistance tasks.</p>
            ) : (
              <div className="space-y-2.5">
                {requests.map((r) => (
                  <div key={r.id} className="p-3 rounded-xl bg-slate-50 border border-slate-100 text-xs space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-slate-900 capitalize">{r.request_type}</span>
                      <span className="text-[10px] font-bold text-amber-700 uppercase">{r.urgency}</span>
                    </div>
                    <p className="text-slate-600">{r.description}</p>
                    <span className="text-[10px] text-slate-400 block pt-0.5">
                      Resident: {r.user_name || 'Senior Citizen'}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Responder Protocol Quick Reference */}
          <div className="bg-slate-900 text-white rounded-2xl p-5 border border-slate-800 space-y-3 text-xs">
            <h4 className="font-bold text-teal-400 text-sm">Responder Operational SOP</h4>
            <ul className="space-y-2 text-slate-300">
              <li>1. Acknowledge high-priority alerts within <strong>120 seconds</strong>.</li>
              <li>2. Verify medical notes before treating allergy/asthma residents.</li>
              <li>3. Log on-scene timestamp immediately upon arrival.</li>
              <li>4. Closure requires two-party resident verification or supervisor signoff.</li>
            </ul>
          </div>

        </div>

      </div>

    </div>
  );
};
