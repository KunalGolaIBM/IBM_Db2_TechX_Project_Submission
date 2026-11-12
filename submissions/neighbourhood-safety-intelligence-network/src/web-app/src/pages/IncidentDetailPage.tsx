import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { MapPin, Clock, ArrowLeft, RefreshCw, CheckCircle2, AlertCircle, Send } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import { Incident, IncidentStatus, SimilarIncident } from '../types';

export const IncidentDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();

  const [incident, setIncident] = useState<Incident | null>(null);
  const [similar, setSimilar] = useState<SimilarIncident[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Status update state
  const [newStatus, setNewStatus] = useState<IncidentStatus>('responder_en_route');
  const [statusNotes, setStatusNotes] = useState<string>('');
  const [updating, setUpdating] = useState<boolean>(false);

  const fetchIncident = async () => {
    if (!id) return;
    setLoading(true);
    try {
      const data = await api.getIncident(Number(id));
      if (user && (user.role === 'responder' || user.role === 'admin')) {
        // Related reports found by Db2 VECTOR_DISTANCE; empty when vector search is not active.
        api.getSimilarIncidents(Number(id)).then(setSimilar).catch(() => setSimilar([]));
      }
      setIncident(data);
      if (data.status === 'reported') setNewStatus('acknowledged');
      else if (data.status === 'acknowledged') setNewStatus('responder_en_route');
      else if (data.status === 'responder_en_route') setNewStatus('on_scene');
      else if (data.status === 'on_scene') setNewStatus('resolving');
      else if (data.status === 'resolving') setNewStatus('resolved');
    } catch (err: any) {
      setError(err.message || 'Failed to load incident detail.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIncident();
  }, [id]);

  const handleUpdateStatus = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!incident) return;
    setUpdating(true);
    try {
      await api.updateIncidentStatus(incident.id, newStatus, statusNotes);
      setStatusNotes('');
      await fetchIncident();
    } catch (err: any) {
      alert('Error updating status: ' + err.message);
    } finally {
      setUpdating(false);
    }
  };

  const handleAcknowledge = async () => {
    if (!incident) return;
    setUpdating(true);
    try {
      await api.acknowledgeIncident(incident.id);
      await fetchIncident();
    } catch (err: any) {
      alert('Error: ' + err.message);
    } finally {
      setUpdating(false);
    }
  };

  if (loading && !incident) {
    return (
      <div className="max-w-4xl mx-auto py-16 text-center text-slate-500 text-sm">
        <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-teal-600" />
        Loading incident dossier...
      </div>
    );
  }

  if (error || !incident) {
    return (
      <div className="max-w-2xl mx-auto py-16 text-center space-y-4">
        <AlertCircle className="w-10 h-10 text-red-500 mx-auto" />
        <h2 className="text-xl font-bold text-slate-900">{error || 'Incident Not Found'}</h2>
        <Link to="/dashboard" className="inline-flex items-center gap-1.5 text-sm text-teal-600 font-semibold">
          <ArrowLeft className="w-4 h-4" /> Return to Dashboard
        </Link>
      </div>
    );
  }

  const isResponderOrAdmin = user?.role === 'responder' || user?.role === 'admin';
  const isReporter = user?.id === incident.reporter_id;

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      
      {/* Navigation & Header */}
      <div>
        <Link 
          to={isResponderOrAdmin ? "/responder" : "/dashboard"}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-800 transition mb-3"
        >
          <ArrowLeft className="w-4 h-4" /> Back to Dashboard
        </Link>

        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono font-bold text-slate-500 text-xs">{incident.reference_code}</span>
              <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full ${
                incident.priority === 'P1_CRITICAL' ? 'bg-red-100 text-red-700' :
                incident.priority === 'P2_HIGH' ? 'bg-amber-100 text-amber-700' :
                'bg-slate-100 text-slate-700'
              }`}>
                {incident.priority}
              </span>
              <span className="text-xs text-slate-400 capitalize">• {incident.incident_type.replace('_', ' ')}</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 mt-1">{incident.title}</h1>
          </div>

          <div className="flex items-center gap-3">
            <span className={`text-xs font-bold px-3 py-1.5 rounded-xl capitalize ${
              incident.status === 'resolved' ? 'bg-emerald-100 text-emerald-800' :
              incident.status === 'on_scene' ? 'bg-blue-100 text-blue-800' :
              incident.status === 'acknowledged' ? 'bg-amber-100 text-amber-800' :
              'bg-red-100 text-red-800 animate-pulse'
            }`}>
              {incident.status.replace('_', ' ')}
            </span>

            <button
              onClick={fetchIncident}
              className="p-2 text-slate-500 hover:text-slate-800 rounded-xl hover:bg-slate-100 transition border border-slate-200"
              title="Refresh timeline"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Incident Details Card */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-4">
        <div>
          <h3 className="text-xs font-bold uppercase text-slate-400 tracking-wider">Report Description</h3>
          <p className="text-sm text-slate-800 mt-1 leading-relaxed">{incident.description}</p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-3 border-t border-slate-100 text-xs">
          <div>
            <span className="text-slate-400 block">Reported By</span>
            <span className="font-semibold text-slate-800">{incident.reporter_name || 'Resident'}</span>
          </div>
          <div>
            <span className="text-slate-400 block">Location Address</span>
            <span className="font-semibold text-slate-800 flex items-center gap-1 mt-0.5">
              <MapPin className="w-3.5 h-3.5 text-slate-400" />
              {incident.location_address || 'Designated Area'}
            </span>
          </div>
          <div>
            <span className="text-slate-400 block">Assigned Responder</span>
            <span className="font-semibold text-teal-700">{incident.assigned_responder_name || 'Awaiting Claim'}</span>
          </div>
        </div>
      </div>

      {/* Responder / Citizen Action Bar */}
      {incident.status !== 'resolved' && (
        <div className="bg-slate-50 rounded-2xl p-6 border border-slate-200 space-y-4">
          <h3 className="text-sm font-bold text-slate-900">Incident Action & Status Transition</h3>

          {/* Quick acknowledge button for unacknowledged incidents */}
          {isResponderOrAdmin && incident.status === 'reported' && (
            <button
              onClick={handleAcknowledge}
              disabled={updating}
              className="bg-teal-600 hover:bg-teal-500 text-white font-bold px-5 py-2.5 rounded-xl shadow-md transition text-xs flex items-center gap-2"
            >
              <CheckCircle2 className="w-4 h-4" />
              Claim & Acknowledge Incident as {user?.full_name}
            </button>
          )}

          {/* Status update form */}
          {(isResponderOrAdmin || isReporter) && (
            <form onSubmit={handleUpdateStatus} className="space-y-3 pt-2">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="sm:col-span-1">
                  <label className="block text-[11px] font-semibold text-slate-600 mb-1">New Status</label>
                  <select
                    value={newStatus}
                    onChange={(e) => setNewStatus(e.target.value as IncidentStatus)}
                    className="w-full px-3 py-2 text-xs border border-slate-300 rounded-xl bg-white font-medium focus:ring-2 focus:ring-teal-500 outline-none"
                  >
                    {isResponderOrAdmin ? (
                      <>
                        <option value="acknowledged">Acknowledged</option>
                        <option value="responder_en_route">Responder En Route</option>
                        <option value="on_scene">On Scene</option>
                        <option value="resolving">Resolving</option>
                        <option value="resolved">Resolved & Closed</option>
                        <option value="false_alarm">False Alarm</option>
                      </>
                    ) : (
                      <>
                        <option value="resolved">Issue Resolved</option>
                        <option value="false_alarm">False Alarm Cancellation</option>
                      </>
                    )}
                  </select>
                </div>

                <div className="sm:col-span-2">
                  <label className="block text-[11px] font-semibold text-slate-600 mb-1">Operational Notes / Update Reason</label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      placeholder="e.g. Patrol vehicle arrived on scene; area confirmed clear."
                      value={statusNotes}
                      onChange={(e) => setStatusNotes(e.target.value)}
                      className="flex-1 px-3 py-2 text-xs border border-slate-300 rounded-xl focus:ring-2 focus:ring-teal-500 outline-none"
                    />
                    <button
                      type="submit"
                      disabled={updating}
                      className="bg-slate-900 hover:bg-slate-800 text-white font-bold px-4 py-2 rounded-xl text-xs flex items-center gap-1.5 shadow-sm transition disabled:opacity-50"
                    >
                      <Send className="w-3.5 h-3.5 text-teal-400" />
                      Post
                    </button>
                  </div>
                </div>
              </div>
            </form>
          )}
        </div>
      )}

      {similar.length > 0 && (
        <div className="bg-amber-50 rounded-2xl p-5 border border-amber-200 space-y-3">
          <div>
            <h3 className="font-bold text-slate-900 text-sm">Possibly related reports</h3>
            <p className="text-xs text-slate-600">Matched by meaning with IBM Db2 VECTOR_DISTANCE. Check for duplicates before dispatching.</p>
          </div>
          <ul className="space-y-2">
            {similar.map((s) => (
              <li key={s.id}>
                <Link to={`/incidents/${s.id}`} className="flex items-center justify-between gap-3 bg-white rounded-xl border border-amber-100 px-3 py-2 hover:border-amber-300">
                  <span className="text-sm text-slate-800">
                    <span className="font-mono text-xs text-slate-500 mr-2">{s.reference_code}</span>{s.title}
                  </span>
                  <span className="text-xs text-slate-600 whitespace-nowrap">
                    {s.same_location && <strong className="text-amber-800">Same location · </strong>}
                    {Math.round(s.similarity * 100)}% similar · {s.status.replace(/_/g, ' ')}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Chronological Audit Timeline */}
      <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-6">
        <div className="flex items-center gap-2">
          <Clock className="w-4 h-4 text-teal-600" />
          <h3 className="font-bold text-slate-900 text-sm">Chronological Audit Timeline</h3>
        </div>

        <div className="relative pl-6 space-y-6 before:content-[''] before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">
          {incident.status_history.map((h, i) => (
            <div key={h.id || i} className="relative group">
              {/* Dot */}
              <div className={`absolute -left-6 top-1 w-4 h-4 rounded-full border-2 border-white shadow-sm ${
                h.status === 'resolved' ? 'bg-emerald-500' :
                h.status === 'on_scene' ? 'bg-blue-500' :
                h.status === 'acknowledged' ? 'bg-amber-500' :
                'bg-red-500'
              }`} />

              <div className="bg-slate-50 rounded-xl p-3.5 border border-slate-100 space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-bold text-slate-900 capitalize">{h.status.replace('_', ' ')}</span>
                  <span className="text-[11px] text-slate-400 font-mono">
                    {new Date(h.created_at).toLocaleString()}
                  </span>
                </div>
                <p className="text-xs text-slate-600 mt-1">{h.notes || 'Status changed.'}</p>
                <span className="text-[10px] text-slate-400 block pt-1">
                  Logged by: <strong className="text-slate-700">{h.updated_by_name || 'System'}</strong>
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

    </div>
  );
};
