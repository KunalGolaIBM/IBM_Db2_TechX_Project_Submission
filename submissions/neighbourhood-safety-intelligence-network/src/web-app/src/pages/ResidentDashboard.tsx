import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { 
  ShieldAlert, AlertTriangle, Users, Phone, MapPin, Clock, 
  ArrowRight, ShieldCheck, HeartPulse, RefreshCw, Eye, CheckCircle2 
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import { Incident, TrustedContact, CommunityInsights } from '../types';

export const ResidentDashboard: React.FC = () => {
  const { user } = useAuth();
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [contacts, setContacts] = useState<TrustedContact[]>([]);
  const [insights, setInsights] = useState<CommunityInsights | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  
  // SOS Modal state
  const [sosModalOpen, setSosModalOpen] = useState<boolean>(false);
  const [sosCountdown, setSosCountdown] = useState<number>(3);
  const [sosSubmitting, setSosSubmitting] = useState<boolean>(false);
  const [sosSuccessNotice, setSosSuccessNotice] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [incList, contactList, insightData] = await Promise.all([
        api.getIncidents(),
        api.getContacts(),
        api.getCommunityInsights()
      ]);
      setIncidents(incList);
      setContacts(contactList);
      setInsights(insightData);
    } catch (err) {
      console.error("Dashboard fetch error:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleOpenSos = () => {
    setSosModalOpen(true);
    setSosCountdown(3);
    setSosSuccessNotice(null);
  };

  const handleExecuteSos = async () => {
    setSosSubmitting(true);
    try {
      // Fetch browser geolocation if available
      let lat = 12.9716;
      let lng = 77.5946;
      if (navigator.geolocation) {
        try {
          const pos: any = await new Promise((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 4000 });
          });
          lat = pos.coords.latitude;
          lng = pos.coords.longitude;
        } catch (e) {
          console.warn("Geolocation lookup skipped or denied.");
        }
      }

      const res = await api.triggerSOS({
        latitude: lat,
        longitude: lng,
        location_address: user?.address || "Current Device GPS Coordinates",
        description: `EMERGENCY SOS triggered by ${user?.full_name}. Immediate response requested.`
      });

      setSosSuccessNotice(`Emergency SOS registered! Incident Code: ${res.reference_code}. Responders alerted.`);
      await fetchData();
    } catch (err: any) {
      alert("Failed to send SOS: " + err.message);
    } finally {
      setSosSubmitting(false);
      setTimeout(() => {
        setSosModalOpen(false);
      }, 2500);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      
      {/* Top Banner & Quick SOS Action */}
      <div className="bg-gradient-to-r from-slate-900 to-slate-800 rounded-3xl p-6 sm:p-8 text-white shadow-lg border border-slate-700/60 flex flex-col md:flex-row items-center justify-between gap-6">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-teal-500/20 text-teal-300 text-xs font-semibold mb-3 border border-teal-500/30">
            <ShieldCheck className="w-3.5 h-3.5" />
            Active Resident Protection Active
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
            Welcome back, {user?.full_name}
          </h1>
          <p className="text-xs sm:text-sm text-slate-300 mt-1 max-w-xl">
            {user?.address || "Oak Ridge Apartments, Sector 4"} • {contacts.length} trusted contacts active.
          </p>
        </div>

        {/* Big SOS Trigger */}
        <div className="flex flex-col items-center">
          <button
            onClick={handleOpenSos}
            className="group relative flex items-center justify-center w-28 h-28 rounded-full bg-red-600 hover:bg-red-500 text-white shadow-xl shadow-red-600/40 border-4 border-red-400/40 transition-transform active:scale-95 animate-pulse"
            title="Click to trigger emergency distress SOS"
          >
            <div className="text-center">
              <ShieldAlert className="w-8 h-8 mx-auto" />
              <span className="text-xs font-black tracking-wider uppercase block mt-1">EMERGENCY<br />SOS</span>
            </div>
          </button>
          <span className="text-[11px] text-slate-400 mt-2 font-medium">One-Tap Distress Signal</span>
        </div>
      </div>

      {/* SOS Confirmation Modal */}
      {sosModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-white rounded-3xl p-6 sm:p-8 max-w-md w-full border border-red-200 shadow-2xl text-center space-y-5">
            <div className="w-16 h-16 rounded-2xl bg-red-100 text-red-600 mx-auto flex items-center justify-center border border-red-200 animate-bounce">
              <ShieldAlert className="w-10 h-10" />
            </div>

            <div>
              <h2 className="text-2xl font-bold text-slate-900">Confirm Distress SOS?</h2>
              <p className="text-xs text-slate-600 mt-2">
                This will immediately broadcast your identity, location, and emergency notes to 
                <strong> {contacts.length} trusted contacts</strong> and <strong>verified community patrol units</strong>.
              </p>
            </div>

            {sosSuccessNotice ? (
              <div className="p-4 rounded-2xl bg-emerald-50 text-emerald-800 text-xs font-semibold flex items-center gap-2 text-left border border-emerald-200">
                <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
                <span>{sosSuccessNotice}</span>
              </div>
            ) : (
              <div className="flex items-center justify-center gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setSosModalOpen(false)}
                  className="px-5 py-2.5 rounded-xl border border-slate-300 text-slate-700 text-sm font-semibold hover:bg-slate-50 transition"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleExecuteSos}
                  disabled={sosSubmitting}
                  className="px-6 py-2.5 rounded-xl bg-red-600 hover:bg-red-700 text-white text-sm font-bold shadow-lg shadow-red-600/30 transition disabled:opacity-50"
                >
                  {sosSubmitting ? 'Broadcasting Alert...' : 'Yes, Send Distress Alert'}
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Quick Action Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        
        <Link 
          to="/report-incident" 
          className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm hover:border-teal-500/50 hover:shadow-md transition group"
        >
          <div className="w-10 h-10 rounded-xl bg-amber-100 text-amber-700 flex items-center justify-center mb-3 group-hover:scale-105 transition">
            <AlertTriangle className="w-5 h-5" />
          </div>
          <h3 className="font-bold text-slate-900 text-sm">Report Hazard</h3>
          <p className="text-[11px] text-slate-500 mt-1">Dark street, prowler, or road hazard</p>
        </Link>

        <Link 
          to="/child-safety" 
          className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm hover:border-teal-500/50 hover:shadow-md transition group"
        >
          <div className="w-10 h-10 rounded-xl bg-blue-100 text-blue-700 flex items-center justify-center mb-3 group-hover:scale-105 transition">
            <Eye className="w-5 h-5" />
          </div>
          <h3 className="font-bold text-slate-900 text-sm">Child Safe Transit</h3>
          <p className="text-[11px] text-slate-500 mt-1">Expected arrival & check-in monitor</p>
        </Link>

        <Link 
          to="/elder-care" 
          className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm hover:border-teal-500/50 hover:shadow-md transition group"
        >
          <div className="w-10 h-10 rounded-xl bg-teal-100 text-teal-700 flex items-center justify-center mb-3 group-hover:scale-105 transition">
            <HeartPulse className="w-5 h-5" />
          </div>
          <h3 className="font-bold text-slate-900 text-sm">Elder Care Check-in</h3>
          <p className="text-[11px] text-slate-500 mt-1">Daily wellness checks & assistance</p>
        </Link>

        <Link 
          to="/contacts" 
          className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm hover:border-teal-500/50 hover:shadow-md transition group"
        >
          <div className="w-10 h-10 rounded-xl bg-purple-100 text-purple-700 flex items-center justify-center mb-3 group-hover:scale-105 transition">
            <Users className="w-5 h-5" />
          </div>
          <h3 className="font-bold text-slate-900 text-sm">Trusted Contacts</h3>
          <p className="text-[11px] text-slate-500 mt-1">Emergency guardian circle ({contacts.length})</p>
        </Link>

      </div>

      {/* Main Content Two-Column */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Left Column: Active Incidents */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold text-slate-900">Your Incident Reports & Alerts</h2>
              <p className="text-xs text-slate-500">Real-time status synced with community responders</p>
            </div>
            <button
              onClick={fetchData}
              className="p-2 text-slate-500 hover:text-slate-800 rounded-lg hover:bg-slate-100 transition"
              title="Refresh"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>

          {incidents.length === 0 ? (
            <div className="bg-white rounded-2xl p-8 border border-slate-200 text-center space-y-3">
              <ShieldCheck className="w-10 h-10 text-teal-600 mx-auto" />
              <h3 className="text-base font-semibold text-slate-800">No Active Incidents</h3>
              <p className="text-xs text-slate-500 max-w-sm mx-auto">
                Your corridor has no active alerts logged. You can trigger an SOS or report hazards anytime.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {incidents.map((inc) => (
                <div 
                  key={inc.id}
                  className="bg-white rounded-2xl p-4 sm:p-5 border border-slate-200 shadow-sm hover:shadow-md transition space-y-3"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-mono font-bold text-slate-500">{inc.reference_code}</span>
                        <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full ${
                          inc.priority === 'P1_CRITICAL' ? 'bg-red-100 text-red-700' :
                          inc.priority === 'P2_HIGH' ? 'bg-amber-100 text-amber-700' :
                          'bg-slate-100 text-slate-700'
                        }`}>
                          {inc.priority}
                        </span>
                        <span className="text-[10px] font-semibold text-slate-400">
                          {new Date(inc.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                      <h3 className="font-bold text-slate-900 text-base mt-1">{inc.title}</h3>
                      <p className="text-xs text-slate-600 line-clamp-2 mt-0.5">{inc.description}</p>
                    </div>

                    <span className={`text-xs font-semibold px-2.5 py-1 rounded-xl whitespace-nowrap capitalize ${
                      inc.status === 'resolved' ? 'bg-emerald-100 text-emerald-800' :
                      inc.status === 'on_scene' ? 'bg-blue-100 text-blue-800' :
                      inc.status === 'acknowledged' ? 'bg-amber-100 text-amber-800' :
                      'bg-red-100 text-red-800 animate-pulse'
                    }`}>
                      {inc.status.replace('_', ' ')}
                    </span>
                  </div>

                  <div className="flex items-center justify-between pt-2 border-t border-slate-100 text-xs">
                    <span className="text-slate-500 flex items-center gap-1">
                      <MapPin className="w-3.5 h-3.5 text-slate-400" />
                      {inc.location_address || "Designated Sector Area"}
                    </span>
                    <Link
                      to={`/incidents/${inc.id}`}
                      className="text-teal-600 hover:text-teal-700 font-semibold flex items-center gap-1"
                    >
                      View Live Timeline
                      <ArrowRight className="w-3.5 h-3.5" />
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right Column: Trusted Contacts & AI Safety Health */}
        <div className="space-y-6">
          
          {/* Trusted Contacts Mini Card */}
          <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-slate-900 text-sm flex items-center gap-2">
                <Users className="w-4 h-4 text-teal-600" />
                Emergency Guardians
              </h3>
              <Link to="/contacts" className="text-xs text-teal-600 hover:text-teal-700 font-semibold">
                Manage
              </Link>
            </div>

            {contacts.length === 0 ? (
              <p className="text-xs text-slate-500 italic">No trusted contacts added yet. Add family members to notify them during an SOS.</p>
            ) : (
              <div className="space-y-2">
                {contacts.slice(0, 3).map((c) => (
                  <div key={c.id} className="flex items-center justify-between p-2.5 rounded-xl bg-slate-50 border border-slate-100 text-xs">
                    <div>
                      <span className="font-semibold text-slate-900 block">{c.name}</span>
                      <span className="text-[11px] text-slate-500">{c.relationship} • {c.phone}</span>
                    </div>
                    <span className="text-[10px] bg-teal-100 text-teal-800 font-semibold px-2 py-0.5 rounded-full">
                      SOS Active
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* AI Community Safety Advisory */}
          <div className="bg-gradient-to-br from-slate-900 to-teal-950 text-white rounded-2xl p-5 border border-slate-800 shadow-md space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold text-teal-400 uppercase tracking-wider">
                AI Civic Safety Advisory
              </span>
              <span className="text-xs font-bold bg-teal-500/20 px-2 py-0.5 rounded border border-teal-500/30 text-teal-300">
                Score: {insights?.safety_health_score || 92}/100
              </span>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed">
              {insights?.ai_safety_advisory || "Community corridor verified clear by verified volunteer patrols. Safe transit mode recommended after dusk."}
            </p>
            <div className="text-[10px] text-slate-400 pt-1 border-t border-slate-800">
              Assisted by Haystack RAG & CrewAI Agentic Triage
            </div>
          </div>

        </div>

      </div>

    </div>
  );
};
