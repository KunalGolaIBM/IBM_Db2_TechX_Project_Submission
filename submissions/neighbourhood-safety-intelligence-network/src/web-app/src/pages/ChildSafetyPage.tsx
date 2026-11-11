import React, { useState, useEffect } from 'react';
import { Eye, Plus, MapPin, Clock, CheckCircle2, AlertTriangle, ShieldCheck, RefreshCw } from 'lucide-react';
import { api } from '../services/api';
import { ChildJourney } from '../types';

export const ChildSafetyPage: React.FC = () => {
  const [journeys, setJourneys] = useState<ChildJourney[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);

  // Form
  const [childName, setChildName] = useState('');
  const [origin, setOrigin] = useState('');
  const [destination, setDestination] = useState('');
  const [duration, setDuration] = useState(30);
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);

  const fetchJourneys = async () => {
    setLoading(true);
    try {
      const data = await api.getChildJourneys();
      setJourneys(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJourneys();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.createChildJourney({
        child_name: childName,
        origin,
        destination,
        expected_duration_minutes: duration,
        notes: notes || undefined,
      });
      setChildName('');
      setOrigin('');
      setDestination('');
      setNotes('');
      setModalOpen(false);
      await fetchJourneys();
    } catch (err: any) {
      alert("Error: " + err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleCheckIn = async (journeyId: number, status: string) => {
    try {
      await api.checkInChildJourney(journeyId, {
        status,
        notes: status === 'completed' ? 'Arrived safely at destination.' : 'Delay check-in recorded by guardian.'
      });
      await fetchJourneys();
    } catch (err: any) {
      alert("Check-in error: " + err.message);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-slate-900">Child Safe Transit Monitoring</h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Guardian-monitored journeys with arrival windows and delay escalation protocols.
          </p>
        </div>
        <button
          onClick={() => setModalOpen(true)}
          className="inline-flex items-center gap-2 bg-teal-600 hover:bg-teal-500 text-white font-bold px-4 py-2.5 rounded-xl shadow-md transition text-xs"
        >
          <Plus className="w-4 h-4" /> Start New Journey
        </button>
      </div>

      {/* Journeys List */}
      {journeys.length === 0 ? (
        <div className="bg-white rounded-2xl p-10 border border-slate-200 text-center space-y-3">
          <Eye className="w-12 h-12 text-slate-400 mx-auto" />
          <h3 className="text-base font-semibold text-slate-800">No Active Journeys Monitored</h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            Log school commutes or activity journeys to ensure real-time waypoint alerts and missed-arrival tracking.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {journeys.map((j) => (
            <div key={j.id} className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm space-y-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-bold text-slate-900 text-lg">{j.child_name}</h3>
                    <span className={`text-[10px] font-bold uppercase px-2.5 py-0.5 rounded-full ${
                      j.status === 'completed' ? 'bg-emerald-100 text-emerald-800' :
                      j.status === 'delayed' ? 'bg-amber-100 text-amber-800' :
                      j.status === 'alert_triggered' ? 'bg-red-100 text-red-800 animate-pulse' :
                      'bg-blue-100 text-blue-800'
                    }`}>
                      {j.status.replace('_', ' ')}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-slate-500 mt-1">
                    <MapPin className="w-3.5 h-3.5 text-slate-400" />
                    <span>{j.origin}</span>
                    <span>→</span>
                    <span>{j.destination}</span>
                  </div>
                </div>

                {j.status === 'active' && (
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleCheckIn(j.id, 'completed')}
                      className="inline-flex items-center gap-1.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold px-3 py-1.5 rounded-xl text-xs transition"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" /> Arrived Safely
                    </button>
                    <button
                      onClick={() => handleCheckIn(j.id, 'delayed')}
                      className="inline-flex items-center gap-1.5 bg-amber-600 hover:bg-amber-500 text-white font-bold px-3 py-1.5 rounded-xl text-xs transition"
                    >
                      <AlertTriangle className="w-3.5 h-3.5" /> Flag Delay
                    </button>
                  </div>
                )}
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 pt-3 border-t border-slate-100 text-xs">
                <div>
                  <span className="text-slate-400 block">Expected Arrival</span>
                  <span className="font-semibold text-slate-800">
                    {new Date(j.expected_arrival_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block">Last Check-in</span>
                  <span className="font-semibold text-slate-800">
                    {j.last_check_in ? new Date(j.last_check_in).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Pending'}
                  </span>
                </div>
                <div className="col-span-2 sm:col-span-1">
                  <span className="text-slate-400 block">Corridor Status</span>
                  <span className="font-semibold text-teal-700">Patrols Alerted</span>
                </div>
              </div>

              {j.notes && (
                <div className="bg-slate-50 p-2.5 rounded-xl text-xs text-slate-600 border border-slate-100">
                  <strong className="text-slate-800">Notes:</strong> {j.notes}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-white rounded-3xl p-6 sm:p-8 max-w-md w-full border border-slate-200 shadow-2xl space-y-5">
            <h2 className="text-xl font-bold text-slate-900">Register Child Safe Transit</h2>
            <form onSubmit={handleCreate} className="space-y-4 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Child Name & Age</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Aarav Sen (Age 10)"
                  value={childName}
                  onChange={(e) => setChildName(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-xl focus:ring-2 focus:ring-teal-500 outline-none"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Origin Point</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. St. Xavier's Academy, Sector 2"
                  value={origin}
                  onChange={(e) => setOrigin(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-xl focus:ring-2 focus:ring-teal-500 outline-none"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Destination</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. House 18, Sunset Boulevard, Sector 4"
                  value={destination}
                  onChange={(e) => setDestination(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-xl focus:ring-2 focus:ring-teal-500 outline-none"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Expected Duration (Minutes)</label>
                <input
                  type="number"
                  required
                  min={5}
                  max={180}
                  value={duration}
                  onChange={(e) => setDuration(Number(e.target.value))}
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-xl focus:ring-2 focus:ring-teal-500 outline-none"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Transit Notes (Route, bus number, companions)</label>
                <input
                  type="text"
                  placeholder="e.g. School Bus #14 with driver Mohan"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-xl focus:ring-2 focus:ring-teal-500 outline-none"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-3">
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="px-4 py-2 border border-slate-300 rounded-xl text-slate-700 font-semibold hover:bg-slate-50 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="px-5 py-2 bg-teal-600 hover:bg-teal-500 text-white font-bold rounded-xl shadow-md transition disabled:opacity-50"
                >
                  {saving ? 'Creating...' : 'Start Monitoring'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
