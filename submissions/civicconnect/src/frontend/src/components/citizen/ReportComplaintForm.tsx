import React, { useState } from 'react';
import {
  FileText,
  MapPin,
  Camera,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  Upload,
  ArrowRight,
  Copy,
  Check,
  Building,
  Tag,
  Loader2,
  Trash2,
  Construction,
  Lightbulb,
  Droplets,
  Waves,
  ShieldAlert,
  HelpCircle,
  X
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { CIVIC_CATEGORIES, Complaint, ComplaintPriority } from '../../types';
import { submitComplaint } from '../../services/complaintService';
import { SAMPLE_CIVIC_PHOTOS } from '../../utils/photoPresets';

interface ReportComplaintFormProps {
  onSuccess: (complaint: Complaint) => void;
  onCancel: () => void;
  initialPreset?: 'pothole' | 'garbage' | 'streetlight' | null;
}

export const ReportComplaintForm: React.FC<ReportComplaintFormProps> = ({
  onSuccess,
  onCancel,
  initialPreset = null
}) => {
  const { userProfile, currentUser } = useAuth();

  const [title, setTitle] = useState(
    initialPreset === 'pothole'
      ? 'Large dangerous pothole on Market Main Road'
      : initialPreset === 'garbage'
      ? 'Overflowing commercial waste dumpster near community park'
      : initialPreset === 'streetlight'
      ? 'Broken streetlight creating pitch dark hazard'
      : ''
  );
  const [description, setDescription] = useState(
    initialPreset === 'pothole'
      ? 'A deep crater-like pothole has formed across the main lane after recent rains. Multiple two-wheelers and cars have sustained tire damage. It poses an immediate road accident risk at night.'
      : initialPreset === 'garbage'
      ? 'Municipal bins have not been cleared for over 4 days. Domestic and commercial waste is spilling onto the pedestrian sidewalk, emitting foul stench and attracting stray animals.'
      : initialPreset === 'streetlight'
      ? 'The electrical luminaire atop pole #34 is completely dead. The entire road intersection is pitch dark after 7 PM, making it unsafe for pedestrians and residents.'
      : ''
  );
  const [category, setCategory] = useState(
    initialPreset === 'pothole'
      ? 'Road Damage / Potholes'
      : initialPreset === 'garbage'
      ? 'Garbage Collection'
      : initialPreset === 'streetlight'
      ? 'Streetlight Problems'
      : 'Road Damage / Potholes'
  );
  const [location, setLocation] = useState(
    initialPreset ? 'Sector 4, Central Avenue, Near City Market' : ''
  );
  const [landmark, setLandmark] = useState(
    initialPreset ? 'Opposite Bank of India ATM, Pillar 42' : ''
  );
  const [priority, setPriority] = useState<ComplaintPriority>(
    initialPreset === 'pothole' ? 'high' : 'medium'
  );
  const [imageUrl, setImageUrl] = useState<string>(
    initialPreset ? SAMPLE_CIVIC_PHOTOS[initialPreset] : ''
  );

  // AI Assistant states
  const [isClassifying, setIsClassifying] = useState(false);
  const [aiSuggestions, setAiSuggestions] = useState<{
    category: string;
    department: string;
    priority: ComplaintPriority;
    keywords: string[];
    summary: string;
    aiPowered: boolean;
  } | null>(null);
  const [aiError, setAiError] = useState<string | null>(null);

  // Submission state
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submittedComplaint, setSubmittedComplaint] = useState<Complaint | null>(null);
  const [copiedId, setCopiedId] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Trigger Gemini AI classification
  const handleAiClassification = async () => {
    if (!description.trim() && !title.trim()) {
      setAiError('Please enter a brief title or description first.');
      return;
    }
    setIsClassifying(true);
    setAiError(null);

    try {
      const res = await fetch('/api/ai/classify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, description })
      });
      if (!res.ok) throw new Error('AI classification request failed');
      const data = await res.json();
      setAiSuggestions(data);
    } catch (err: any) {
      console.warn('AI classification fallback error:', err);
      setAiError('Could not connect to Gemini service. You can select your category manually.');
    } finally {
      setIsClassifying(false);
    }
  };

  const applyAiSuggestions = () => {
    if (!aiSuggestions) return;
    setCategory(aiSuggestions.category);
    setPriority(aiSuggestions.priority);
  };

  // Image upload handler
  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith('image/')) {
      alert('Please upload a valid image file (JPEG, PNG, WebP).');
      return;
    }

    if (file.size > 4 * 1024 * 1024) {
      alert('Image file size must be under 4MB.');
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      setImageUrl(reader.result as string);
    };
    reader.readAsDataURL(file);
  };

  const handleFormSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    if (!title.trim()) {
      setErrorMsg('Please enter a complaint title.');
      return;
    }
    if (!description.trim()) {
      setErrorMsg('Please enter a detailed description.');
      return;
    }
    if (!location.trim()) {
      setErrorMsg('Please specify the location or locality.');
      return;
    }

    setIsSubmitting(true);
    try {
      const citizenUid = userProfile?.uid || currentUser?.uid || 'demo-citizen-rahul';
      const citizenName = userProfile?.name || currentUser?.displayName || 'Rahul Sharma (Citizen)';
      const citizenEmail = userProfile?.email || currentUser?.email || 'citizen.rahul@civicconnect.local';

      const result = await submitComplaint({
        userId: citizenUid,
        citizenName,
        citizenEmail,
        title,
        description,
        category,
        location,
        landmark,
        imageUrl,
        priority,
        aiSummary: aiSuggestions?.summary,
        aiKeywords: aiSuggestions?.keywords
      });

      setSubmittedComplaint(result);
    } catch (err: any) {
      console.error('Failed to submit complaint:', err);
      setErrorMsg(err.message || 'Failed to submit complaint to Firestore. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCopyId = () => {
    if (!submittedComplaint) return;
    navigator.clipboard.writeText(submittedComplaint.complaintId);
    setCopiedId(true);
    setTimeout(() => setCopiedId(false), 2000);
  };

  // SUCCESS SCREEN
  if (submittedComplaint) {
    return (
      <div className="max-w-2xl mx-auto my-8 p-6 sm:p-8 bg-white border border-slate-200/90 rounded-2xl shadow-xl text-center">
        <div className="w-16 h-16 bg-teal-100 text-teal-700 rounded-full flex items-center justify-center mx-auto mb-4 ring-8 ring-teal-50">
          <CheckCircle2 className="w-10 h-10" />
        </div>

        <span className="text-xs font-bold uppercase tracking-wider text-teal-700 bg-teal-50 px-3 py-1 rounded-full border border-teal-200">
          Complaint Successfully Registered
        </span>

        <h2 className="text-2xl font-bold text-slate-900 mt-3">Grievance Ticket Generated</h2>
        <p className="text-sm text-slate-600 mt-1 max-w-md mx-auto">
          Your complaint has been logged in the municipal database and routed for administrative review and department assignment.
        </p>

        {/* Complaint ID card */}
        <div className="mt-6 p-4 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between max-w-md mx-auto">
          <div className="text-left">
            <p className="text-[11px] font-semibold uppercase text-slate-500">Official Tracking ID</p>
            <p className="text-xl font-mono font-bold text-teal-800">{submittedComplaint.complaintId}</p>
          </div>
          <button
            type="button"
            onClick={handleCopyId}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white border border-slate-300 text-slate-700 hover:bg-slate-100 text-xs font-medium transition"
          >
            {copiedId ? <Check className="w-4 h-4 text-emerald-600" /> : <Copy className="w-4 h-4" />}
            <span>{copiedId ? 'Copied' : 'Copy ID'}</span>
          </button>
        </div>

        <div className="mt-6 text-left bg-slate-50/70 p-4 rounded-xl border border-slate-200 text-xs space-y-2 max-w-md mx-auto">
          <div className="flex justify-between">
            <span className="text-slate-500">Category:</span>
            <span className="font-semibold text-slate-800">{submittedComplaint.category}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Location:</span>
            <span className="font-semibold text-slate-800">{submittedComplaint.location}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Priority:</span>
            <span className="font-semibold capitalize text-amber-700">{submittedComplaint.priority}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Initial Status:</span>
            <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold bg-blue-100 text-blue-800">
              Submitted
            </span>
          </div>
        </div>

        <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3">
          <button
            type="button"
            onClick={() => onSuccess(submittedComplaint)}
            className="w-full sm:w-auto px-6 py-2.5 rounded-xl bg-teal-600 hover:bg-teal-500 text-white text-sm font-semibold shadow-md transition flex items-center justify-center gap-2"
          >
            <span>View Timeline & Progress</span>
            <ArrowRight className="w-4 h-4" />
          </button>
          <button
            type="button"
            onClick={() => {
              setSubmittedComplaint(null);
              setTitle('');
              setDescription('');
              setImageUrl('');
            }}
            className="w-full sm:w-auto px-5 py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-sm font-medium transition"
          >
            Report Another Issue
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto my-6 p-6 sm:p-8 bg-white border border-slate-200/90 rounded-2xl shadow-sm">
      <div className="border-b border-slate-200 pb-4 mb-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-teal-50 text-teal-700 flex items-center justify-center border border-teal-200">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-slate-900">Report a Civic Problem</h2>
              <p className="text-xs text-slate-500">Submit municipal infrastructure or sanitation grievance with evidence</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onCancel}
            className="text-slate-400 hover:text-slate-600 p-1 rounded-lg"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>

      {errorMsg && (
        <div className="mb-6 p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold">Submission Error</p>
            <p className="text-xs mt-0.5">{errorMsg}</p>
          </div>
        </div>
      )}

      <form onSubmit={handleFormSubmit} className="space-y-6">
        {/* Title */}
        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1.5">
            Complaint Title <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Deep pothole causing accidents near main market crossroad"
            maxLength={180}
            required
            className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-slate-900 placeholder:text-slate-400 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent transition"
          />
        </div>

        {/* Description */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-700">
              Detailed Description <span className="text-red-500">*</span>
            </label>
            <span className="text-xs text-slate-400">{description.length}/2000</span>
          </div>
          <textarea
            rows={4}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Provide exact details: dimensions, hazards, duration of issue, impact on traffic or public hygiene..."
            maxLength={2000}
            required
            className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-slate-900 placeholder:text-slate-400 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent transition"
          />

          {/* AI Complaint Assistant Trigger */}
          <div className="mt-2 flex items-center justify-between">
            <p className="text-xs text-slate-500">Need help categorizing and assigning this complaint?</p>
            <button
              type="button"
              onClick={handleAiClassification}
              disabled={isClassifying || (!title.trim() && !description.trim())}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-teal-50 hover:bg-teal-100 border border-teal-200 text-teal-800 text-xs font-semibold disabled:opacity-50 transition"
            >
              {isClassifying ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-teal-600" />
                  <span>Analyzing with Gemini...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-3.5 h-3.5 text-teal-600" />
                  <span>Smart Classify with Gemini</span>
                </>
              )}
            </button>
          </div>

          {aiError && (
            <p className="text-xs text-amber-600 mt-1.5">{aiError}</p>
          )}

          {/* AI Suggestions Preview Card */}
          {aiSuggestions && (
            <div className="mt-3 p-4 bg-teal-50/70 border border-teal-200 rounded-xl space-y-2.5 animate-fadeIn">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <Sparkles className="w-4 h-4 text-teal-600" />
                  <span className="text-xs font-bold text-teal-900 uppercase tracking-wide">
                    Gemini AI Suggestions
                  </span>
                </div>
                <button
                  type="button"
                  onClick={applyAiSuggestions}
                  className="px-2.5 py-1 text-xs font-semibold rounded bg-teal-600 hover:bg-teal-500 text-white transition shadow-sm"
                >
                  Apply Suggestions
                </button>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs">
                <div className="bg-white p-2 rounded-lg border border-teal-100">
                  <span className="text-slate-400 block text-[10px] font-medium">Category</span>
                  <span className="font-semibold text-slate-800">{aiSuggestions.category}</span>
                </div>
                <div className="bg-white p-2 rounded-lg border border-teal-100">
                  <span className="text-slate-400 block text-[10px] font-medium">Target Department</span>
                  <span className="font-semibold text-slate-800">{aiSuggestions.department}</span>
                </div>
                <div className="bg-white p-2 rounded-lg border border-teal-100">
                  <span className="text-slate-400 block text-[10px] font-medium">Suggested Priority</span>
                  <span className="font-semibold capitalize text-teal-700">{aiSuggestions.priority}</span>
                </div>
              </div>

              {aiSuggestions.summary && (
                <p className="text-xs text-slate-600 bg-white/80 p-2 rounded-lg border border-teal-100">
                  <strong className="text-slate-700">Executive Summary:</strong> {aiSuggestions.summary}
                </p>
              )}

              {aiSuggestions.keywords && aiSuggestions.keywords.length > 0 && (
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-[10px] text-slate-400 font-medium">Keywords:</span>
                  {aiSuggestions.keywords.map((kw, i) => (
                    <span key={i} className="text-[10px] bg-teal-100/70 text-teal-800 px-1.5 py-0.5 rounded">
                      #{kw}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Category & Priority in 2 Columns */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1.5">
              Complaint Category <span className="text-red-500">*</span>
            </label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-slate-900 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent transition bg-white"
            >
              {CIVIC_CATEGORIES.map((cat) => (
                <option key={cat.name} value={cat.name}>
                  {cat.name} &rarr; ({cat.defaultDepartment})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1.5">
              Priority Suggestion
            </label>
            <select
              value={priority}
              onChange={(e) => setPriority(e.target.value as ComplaintPriority)}
              className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-slate-900 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent transition bg-white capitalize"
            >
              <option value="low">Low (Standard maintenance, minor aesthetics)</option>
              <option value="medium">Medium (Regular civic issues)</option>
              <option value="high">High (Traffic block, health hazard, severe damage)</option>
              <option value="urgent">Urgent (Immediate public safety danger)</option>
            </select>
          </div>
        </div>

        {/* Location & Landmark */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1.5">
              Location / Locality <span className="text-red-500">*</span>
            </label>
            <div className="relative">
              <MapPin className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
              <input
                type="text"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="e.g. Sector 4 Market Road, Near Block B"
                required
                className="w-full pl-9 pr-3.5 py-2.5 rounded-xl border border-slate-300 text-slate-900 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent transition"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1.5">
              Nearest Landmark (Optional)
            </label>
            <input
              type="text"
              value={landmark}
              onChange={(e) => setLandmark(e.target.value)}
              placeholder="e.g. Opposite Post Office or Gate #2"
              className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-slate-900 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent transition"
            />
          </div>
        </div>

        {/* Photograph Evidence Upload */}
        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1.5">
            Photographic Evidence (Recommended)
          </label>

          {/* Quick preset buttons for instant evaluation */}
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <span className="text-xs text-slate-500">Quick Test Presets:</span>
            <button
              type="button"
              onClick={() => setImageUrl(SAMPLE_CIVIC_PHOTOS.pothole)}
              className="text-xs px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-300 font-medium transition"
            >
              Use Pothole Photo
            </button>
            <button
              type="button"
              onClick={() => setImageUrl(SAMPLE_CIVIC_PHOTOS.garbage)}
              className="text-xs px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-300 font-medium transition"
            >
              Use Garbage Photo
            </button>
            <button
              type="button"
              onClick={() => setImageUrl(SAMPLE_CIVIC_PHOTOS.streetlight)}
              className="text-xs px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-300 font-medium transition"
            >
              Use Streetlight Photo
            </button>
          </div>

          {imageUrl ? (
            <div className="relative rounded-xl overflow-hidden border border-slate-200 max-h-60 bg-slate-900 group">
              <img src={imageUrl} alt="Uploaded evidence" className="w-full h-56 object-cover" />
              <button
                type="button"
                onClick={() => setImageUrl('')}
                className="absolute top-2 right-2 p-1.5 bg-red-600 text-white rounded-lg shadow-md hover:bg-red-700 transition"
                title="Remove photo"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <div className="border-2 border-dashed border-slate-300 rounded-xl p-6 text-center hover:border-teal-500 transition cursor-pointer relative bg-slate-50/50">
              <input
                type="file"
                accept="image/*"
                onChange={handleImageUpload}
                className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
              />
              <Camera className="w-8 h-8 text-slate-400 mx-auto mb-2" />
              <p className="text-xs font-semibold text-slate-700">Click to upload or drag photo evidence</p>
              <p className="text-[11px] text-slate-400 mt-0.5">Supports PNG, JPG, WebP up to 4MB</p>
            </div>
          )}
        </div>

        {/* Form Actions */}
        <div className="pt-4 border-t border-slate-200 flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            className="px-5 py-2.5 rounded-xl border border-slate-300 text-slate-700 hover:bg-slate-100 text-sm font-medium transition"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isSubmitting}
            className="px-6 py-2.5 rounded-xl bg-teal-600 hover:bg-teal-500 text-white text-sm font-semibold shadow-md transition disabled:opacity-50 flex items-center gap-2"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Registering Complaint...</span>
              </>
            ) : (
              <>
                <CheckCircle2 className="w-4 h-4" />
                <span>Submit Grievance</span>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
};
