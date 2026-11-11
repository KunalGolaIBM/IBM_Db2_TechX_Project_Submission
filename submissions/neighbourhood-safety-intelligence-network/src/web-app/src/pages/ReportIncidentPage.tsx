import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  AlertTriangle, Shield, MapPin, Sparkles, CheckCircle2, 
  HelpCircle, ArrowRight, Loader2, BookOpen, AlertCircle 
} from 'lucide-react';
import { api } from '../services/api';
import { AIAnalysisResult } from '../types';

export const ReportIncidentPage: React.FC = () => {
  const navigate = useNavigate();

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [incidentType, setIncidentType] = useState('hazard');
  const [priority, setPriority] = useState('P2_HIGH');
  const [locationAddress, setLocationAddress] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // AI Assistant state
  const [analyzing, setAnalyzing] = useState(false);
  const [aiResult, setAiResult] = useState<AIAnalysisResult | null>(null);

  const handleRunAiTriage = async () => {
    if (!description || description.length < 5) {
      alert("Please enter a short description first so the AI can analyze the incident.");
      return;
    }
    setAnalyzing(true);
    try {
      const res = await api.getIncidentAIAssistance(description, incidentType, locationAddress);
      setAiResult(res);
      if (res.suggested_priority) {
        setPriority(res.suggested_priority);
      }
      if (res.parsed_category) {
        setIncidentType(res.parsed_category);
      }
      if (res.extracted_location && !locationAddress) {
        setLocationAddress(res.extracted_location);
      }
    } catch (err: any) {
      console.error("AI assistance failed:", err);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      const incident = await api.createIncident({
        title,
        description,
        incident_type: incidentType,
        priority,
        location_address: locationAddress || undefined,
      });
      navigate(`/incidents/${incident.id}`);
    } catch (err: any) {
      setError(err.message || 'Failed to submit incident report.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold text-slate-900">Report an Incident or Hazard</h1>
        <p className="text-xs sm:text-sm text-slate-500 mt-1">
          Submit verified details to alert neighbourhood responders, guardians, and municipal authorities.
        </p>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0 text-red-500" />
          <span>{error}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Form Column */}
        <form onSubmit={handleSubmit} className="lg:col-span-2 space-y-5 bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Incident Category</label>
            <select
              value={incidentType}
              onChange={(e) => setIncidentType(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-slate-300 rounded-xl focus:ring-2 focus:ring-teal-500 outline-none bg-white"
            >
              <option value="hazard">Infrastructure Hazard (Broken light, blocked road, open pit)</option>
              <option value="suspicious_activity">Suspicious Activity (Prowler, unverified loitering)</option>
              <option value="medical">Medical Assistance Needed</option>
              <option value="child_alert">Child Safety / Overdue Transit Alert</option>
              <option value="elder_welfare">Senior Citizen Welfare Request</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Incident Summary Title</label>
            <input
              type="text"
              required
              placeholder="e.g. Broken streetlamp creating dark zone on Lane 4"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-slate-300 rounded-xl focus:ring-2 focus:ring-teal-500 outline-none"
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-xs font-semibold text-slate-700">Detailed Description</label>
              <button
                type="button"
                onClick={handleRunAiTriage}
                disabled={analyzing || !description}
                className="text-xs text-teal-700 hover:text-teal-800 font-semibold flex items-center gap-1.5 disabled:opacity-40"
              >
                {analyzing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5 text-teal-600" />}
                Analyze with CrewAI Triage
              </button>
            </div>
            <textarea
              required
              rows={4}
              placeholder="Describe what occurred, any hazards, landmarks, or vehicle details..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-slate-300 rounded-xl focus:ring-2 focus:ring-teal-500 outline-none resize-none"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Specific Location / Landmark</label>
            <div className="relative">
              <MapPin className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
              <input
                type="text"
                placeholder="e.g. Opposite Sector 4 Community Park Gate 2"
                value={locationAddress}
                onChange={(e) => setLocationAddress(e.target.value)}
                className="w-full pl-9 pr-3 py-2 text-sm border border-slate-300 rounded-xl focus:ring-2 focus:ring-teal-500 outline-none"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">Preliminary Priority</label>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
              {['P1_CRITICAL', 'P2_HIGH', 'P3_MODERATE', 'P4_ADVISORY'].map((lvl) => (
                <button
                  key={lvl}
                  type="button"
                  onClick={() => setPriority(lvl)}
                  className={`py-2 px-3 rounded-xl font-bold border transition ${
                    priority === lvl 
                      ? 'bg-slate-900 text-white border-slate-900' 
                      : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50'
                  }`}
                >
                  {lvl.replace('_', ' ')}
                </button>
              ))}
            </div>
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full py-3 px-4 bg-teal-600 hover:bg-teal-500 text-white font-bold rounded-xl shadow-md transition disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {submitting ? 'Registering Incident...' : 'Submit Incident to Responders'}
            <ArrowRight className="w-4 h-4" />
          </button>

        </form>

        {/* AI Assistant Column */}
        <div className="space-y-4">
          <div className="bg-slate-900 text-white p-5 rounded-2xl border border-slate-800 shadow-md space-y-4">
            <div className="flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-teal-400" />
              <h3 className="font-bold text-sm">CrewAI & Haystack Triage</h3>
            </div>

            {aiResult ? (
              <div className="space-y-3 text-xs text-slate-300">
                <div className="bg-slate-800/80 p-3 rounded-xl border border-slate-700">
                  <span className="text-slate-400 block text-[10px] uppercase font-bold">Suggested Priority</span>
                  <span className="text-amber-400 font-bold text-sm">{aiResult.suggested_priority}</span>
                  <p className="text-[11px] text-slate-300 mt-1">{aiResult.triage_reasoning}</p>
                </div>

                {aiResult.missing_critical_info.length > 0 && (
                  <div className="bg-red-950/40 p-3 rounded-xl border border-red-900/40">
                    <span className="text-red-400 font-semibold block mb-1">Missing Critical Information:</span>
                    <ul className="list-disc list-inside space-y-1 text-slate-300 text-[11px]">
                      {aiResult.missing_critical_info.map((m, i) => (
                        <li key={i}>{m}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {aiResult.immediate_safety_checklist.length > 0 && (
                  <div className="bg-slate-800/80 p-3 rounded-xl border border-slate-700">
                    <span className="text-teal-400 font-semibold block mb-1">Immediate Safety Actions:</span>
                    <ul className="space-y-1 text-slate-300 text-[11px]">
                      {aiResult.immediate_safety_checklist.map((a, i) => (
                        <li key={i} className="flex items-start gap-1.5">
                          <CheckCircle2 className="w-3 h-3 text-teal-400 shrink-0 mt-0.5" />
                          <span>{a}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {aiResult.retrieved_civic_protocols.length > 0 && (
                  <div className="bg-slate-800/80 p-3 rounded-xl border border-slate-700">
                    <span className="text-teal-400 font-semibold block mb-1 flex items-center gap-1">
                      <BookOpen className="w-3 h-3" />
                      Retrieved Municipal Protocol:
                    </span>
                    <p className="text-slate-200 font-medium text-[11px]">
                      {aiResult.retrieved_civic_protocols[0].title}
                    </p>
                    <span className="text-[10px] text-slate-400 block mt-0.5">
                      Source: {aiResult.retrieved_civic_protocols[0].source}
                    </span>
                  </div>
                )}

                <p className="text-[10px] text-slate-500 italic pt-1">
                  {aiResult.advisory_notice}
                </p>
              </div>
            ) : (
              <div className="text-xs text-slate-400 space-y-2 py-4">
                <p>
                  Type your incident description and click <strong>"Analyze with CrewAI Triage"</strong> to receive real-time assistance.
                </p>
                <ul className="space-y-1.5 text-[11px]">
                  <li>• Checks for missing location details</li>
                  <li>• Recommends priority level based on risk</li>
                  <li>• Retrieves official civic safety SOPs via Haystack RAG</li>
                </ul>
              </div>
            )}
          </div>
        </div>

      </div>

    </div>
  );
};
