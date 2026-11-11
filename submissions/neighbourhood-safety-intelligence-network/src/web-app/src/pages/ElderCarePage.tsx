import React, { useState, useEffect } from 'react';
import { CheckCircle2, Plus, Clock, ShoppingBag, Pill, RefreshCw } from 'lucide-react';
import { api } from '../services/api';
import { ElderCheckIn, AssistanceRequest } from '../types';

export const ElderCarePage: React.FC = () => {
  const [checkins, setCheckins] = useState<ElderCheckIn[]>([]);
  const [requests, setRequests] = useState<AssistanceRequest[]>([]);
  const [loading, setLoading] = useState(true);

  // Assistance modal
  const [modalOpen, setModalOpen] = useState(false);
  const [reqType, setReqType] = useState('medicine');
  const [description, setDescription] = useState('');
  const [urgency, setUrgency] = useState('medium');
  const [saving, setSaving] = useState(false);

  // Checkin action state
  const [checkingIn, setCheckingIn] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [cList, rList] = await Promise.all([
        api.getElderCheckIns(),
        api.getAssistanceRequests()
      ]);
      setCheckins(cList);
      setRequests(rList);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleDailyCheckIn = async (wellness: 'good' | 'needs_assistance') => {
    setCheckingIn(true);
    try {
      await api.submitElderCheckIn({
        wellness_status: wellness,
        notes: wellness === 'good' ? 'Daily wellness confirmed on schedule.' : 'Resident reported mild discomfort or mobility difficulty.'
      });
      await fetchData();
    } catch (err: any) {
      alert("Error: " + err.message);
    } finally {
      setCheckingIn(false);
    }
  };

  const handleCreateRequest = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.createAssistanceRequest({
        request_type: reqType,
        description,
        urgency,
      });
      setDescription('');
      setModalOpen(false);
      await fetchData();
    } catch (err: any) {
      alert("Error: " + err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      
      {/* Header & Quick Daily Checkin */}
      <div className="bg-gradient-to-r from-teal-900 via-slate-900 to-slate-900 text-white rounded-3xl p-6 sm:p-8 shadow-lg border border-teal-800/40 space-y-4">
        <div>
          <span className="text-teal-400 text-xs font-semibold uppercase tracking-wider block">
            Senior Citizen & Vulnerable Resident Care
          </span>
          <h1 className="text-2xl sm:text-3xl font-bold mt-1">Daily Welfare & Assistance</h1>
          <p className="text-xs sm:text-sm text-slate-300 mt-1 max-w-xl">
            Confirm your wellness each day to keep family guardians and volunteer carers assured.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3 pt-2">
          <button
            onClick={() => handleDailyCheckIn('good')}
            disabled={checkingIn}
            className="inline-flex items-center gap-2 bg-teal-500 hover:bg-teal-400 text-slate-950 font-bold px-5 py-3 rounded-xl shadow-lg transition text-xs"
          >
            <CheckCircle2 className="w-4 h-4" />
            {checkingIn ? 'Recording...' : 'I Am Safe & Well Today'}
          </button>
          
          <button
            onClick={() => setModalOpen(true)}
            className="inline-flex items-center gap-2 bg-slate-800 hover:bg-slate-700 text-white font-semibold px-4 py-3 rounded-xl border border-slate-700 transition text-xs"
          >
            <Plus className="w-4 h-4 text-teal-400" />
            Request Community Assistance
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        
        {/* Assistance Requests */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <ShoppingBag className="w-4 h-4 text-teal-600" />
              Assistance Requests
            </h2>
            <button
              onClick={() => setModalOpen(true)}
              className="text-xs font-semibold text-teal-600 hover:text-teal-700"
            >
              + New Request
            </button>
          </div>

          {requests.length === 0 ? (
            <div className="bg-white rounded-2xl p-6 border border-slate-200 text-center text-xs text-slate-500">
              No active assistance requests. Need groceries or medicines? Request above.
            </div>
          ) : (
            <div className="space-y-3">
              {requests.map((r) => (
                <div key={r.id} className="bg-white rounded-2xl p-4 border border-slate-200 shadow-sm space-y-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-bold text-slate-900 capitalize flex items-center gap-1.5">
                      <Pill className="w-3.5 h-3.5 text-teal-600" />
                      {r.request_type} Assistance
                    </span>
                    <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full ${
                      r.status === 'completed' ? 'bg-emerald-100 text-emerald-800' :
                      r.status === 'assigned' ? 'bg-blue-100 text-blue-800' :
                      'bg-amber-100 text-amber-800'
                    }`}>
                      {r.status}
                    </span>
                  </div>
                  <p className="text-xs text-slate-600">{r.description}</p>
                  <div className="text-[11px] text-slate-400 pt-1 border-t border-slate-100 flex items-center justify-between">
                    <span>Priority: <strong className="text-slate-700 uppercase">{r.urgency}</strong></span>
                    <span>Responder: <strong className="text-teal-700">{r.assigned_to_name || 'In Queue'}</strong></span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Checkin History */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <Clock className="w-4 h-4 text-teal-600" />
              Check-in History
            </h2>
            <button
              onClick={fetchData}
              className="p-1.5 text-slate-400 hover:text-slate-600"
              title="Refresh"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>

          {checkins.length === 0 ? (
            <div className="bg-white rounded-2xl p-6 border border-slate-200 text-center text-xs text-slate-500">
              No recent check-in logs recorded.
            </div>
          ) : (
            <div className="space-y-2.5">
              {checkins.slice(0, 5).map((c) => (
                <div key={c.id} className="bg-white rounded-xl p-3 border border-slate-200 shadow-sm flex items-center justify-between text-xs">
                  <div>
                    <span className="font-semibold text-slate-900 block">
                      {c.checked_in_at ? new Date(c.checked_in_at).toLocaleDateString() : 'Scheduled'}
                    </span>
                    <span className="text-[11px] text-slate-500">{c.notes || 'Wellness confirmed'}</span>
                  </div>
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                    c.wellness_status === 'good' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
                  }`}>
                    {c.wellness_status === 'good' ? '✓ Well' : 'Needs Care'}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

      </div>

      {/* Assistance Request Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-white rounded-3xl p-6 sm:p-8 max-w-md w-full border border-slate-200 shadow-2xl space-y-5">
            <h2 className="text-xl font-bold text-slate-900">Request Community Assistance</h2>
            <form onSubmit={handleCreateRequest} className="space-y-4 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Assistance Type</label>
                <select
                  value={reqType}
                  onChange={(e) => setReqType(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-xl focus:ring-2 focus:ring-teal-500 outline-none bg-white"
                >
                  <option value="medicine">Prescription Medicine Delivery</option>
                  <option value="grocery">Essential Groceries & Supplies</option>
                  <option value="mobility">Mobility Escort / Transport</option>
                  <option value="check_in">Physical Knock-and-Verify Check-in</option>
                  <option value="urgent">Urgent Domestic Assistance</option>
                </select>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Description / Specific Items</label>
                <textarea
                  required
                  rows={3}
                  placeholder="e.g. Please pick up Amlodipine 5mg from Apollo Pharmacy."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-xl focus:ring-2 focus:ring-teal-500 outline-none resize-none"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Urgency Level</label>
                <select
                  value={urgency}
                  onChange={(e) => setUrgency(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-xl focus:ring-2 focus:ring-teal-500 outline-none bg-white"
                >
                  <option value="low">Low (Within 24 hours)</option>
                  <option value="medium">Medium (Within 2-4 hours)</option>
                  <option value="high">High (Immediate / Urgent)</option>
                </select>
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
                  {saving ? 'Submitting...' : 'Submit Request'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
};
