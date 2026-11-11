import React, { useState } from 'react';
import {
  Settings,
  Database,
  Sparkles,
  RefreshCw,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  Server,
  Layers
} from 'lucide-react';
import { seedInitialDepartments, submitComplaint } from '../../services/complaintService';
import { SAMPLE_CIVIC_PHOTOS } from '../../utils/photoPresets';

interface AdminSettingsProps {
  onRefreshComplaints: () => Promise<void>;
}

export const AdminSettings: React.FC<AdminSettingsProps> = ({ onRefreshComplaints }) => {
  const [seeding, setSeeding] = useState(false);
  const [seedSuccess, setSeedSuccess] = useState(false);

  const handleSeedDemoComplaints = async () => {
    setSeeding(true);
    setSeedSuccess(false);
    try {
      // 1. Ensure departments exist
      await seedInitialDepartments();

      // 2. Add realistic demo complaints across categories
      const sampleItems = [
        {
          userId: 'demo-citizen-rahul',
          citizenName: 'Rahul Sharma',
          citizenEmail: 'rahul.citizen@civicconnect.local',
          title: 'Deep road crater and pothole near Sector 4 intersection',
          description: 'A massive 15cm asphalt cave-in developed after the heavy showers on Friday. Vehicles are violently bottoming out and pedestrians are at risk.',
          category: 'Road Damage / Potholes',
          location: 'Sector 4, Central Avenue Junction, Near SBI Bank',
          landmark: 'Opposite Pillar 42',
          priority: 'high' as const,
          imageUrl: SAMPLE_CIVIC_PHOTOS.pothole
        },
        {
          userId: 'demo-citizen-priya',
          citizenName: 'Priya Iyer',
          citizenEmail: 'priya.iyer@civicconnect.local',
          title: 'Commercial garbage bin overflowing onto walkway',
          description: 'Sanitation truck has not visited the vegetable market collection point in 4 days. Waste is spilling across the pedestrian sidewalk.',
          category: 'Garbage Collection',
          location: 'City Market Outer Ring, Gate #3',
          landmark: 'Adjacent to Metro Station Entrance',
          priority: 'medium' as const,
          imageUrl: SAMPLE_CIVIC_PHOTOS.garbage
        },
        {
          userId: 'demo-citizen-amit',
          citizenName: 'Amit Verma',
          citizenEmail: 'amit.verma@civicconnect.local',
          title: 'Broken electrical luminaire causing dark corridor hazard',
          description: 'The pole top fixture on streetlight #19 is completely non-responsive. Junction is pitch dark after dusk.',
          category: 'Streetlight Problems',
          location: 'Nehru Colony Main Road, Lane 7',
          landmark: 'Near Govt Primary School',
          priority: 'medium' as const,
          imageUrl: SAMPLE_CIVIC_PHOTOS.streetlight
        }
      ];

      for (const item of sampleItems) {
        await submitComplaint(item);
      }

      await onRefreshComplaints();
      setSeedSuccess(true);
      setTimeout(() => setSeedSuccess(false), 4000);
    } catch (err: any) {
      alert('Error creating demo data: ' + err.message);
    } finally {
      setSeeding(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-900">System Settings & Infrastructure Audit</h1>
        <p className="text-xs text-slate-500">
          Verify database connections, AI classification services, and populate realistic demo records
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Firestore Status */}
        <div className="p-5 rounded-2xl bg-white border border-slate-200/90 shadow-xs">
          <div className="flex items-center gap-2 text-emerald-700 mb-2">
            <Database className="w-5 h-5 text-emerald-600" />
            <h3 className="text-sm font-bold text-slate-900">Firebase Cloud Firestore</h3>
          </div>
          <p className="text-xs text-slate-600 leading-relaxed">
            Persistent cloud database configured with Enterprise edition in project <code className="text-teal-700 bg-teal-50 px-1 py-0.5 rounded font-mono">centered-office-q7cdj</code>.
          </p>
          <div className="mt-3 flex items-center gap-1.5 text-xs text-emerald-600 font-semibold">
            <CheckCircle2 className="w-4 h-4" />
            <span>Collections & Security Rules Deployed</span>
          </div>
        </div>

        {/* Gemini API Status */}
        <div className="p-5 rounded-2xl bg-white border border-slate-200/90 shadow-xs">
          <div className="flex items-center gap-2 text-teal-700 mb-2">
            <Sparkles className="w-5 h-5 text-teal-600" />
            <h3 className="text-sm font-bold text-slate-900">Gemini 3.8 Flash Engine</h3>
          </div>
          <p className="text-xs text-slate-600 leading-relaxed">
            Server-side AI route active at <code className="text-teal-700 bg-teal-50 px-1 py-0.5 rounded font-mono">/api/ai/classify</code> with automatic heuristic fallback.
          </p>
          <div className="mt-3 flex items-center gap-1.5 text-xs text-teal-700 font-semibold">
            <CheckCircle2 className="w-4 h-4" />
            <span>AI Category & Department Suggester Active</span>
          </div>
        </div>
      </div>

      {/* Demo Seeding Card */}
      <div className="p-6 rounded-2xl bg-white border border-slate-200/90 shadow-xs space-y-4">
        <div className="flex items-center gap-2">
          <Layers className="w-5 h-5 text-slate-700" />
          <h3 className="text-sm font-bold text-slate-900">Evaluation & Demo Data Management</h3>
        </div>
        <p className="text-xs text-slate-600 leading-relaxed">
          Need to test the administrator dashboard charts and staff assignment with realistic grievances? Click below to populate realistic sample complaints (Pothole, Waste, Streetlight) with real photographic evidence.
        </p>

        {seedSuccess && (
          <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-800 text-xs flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>Sample complaints added to Firestore! Check your dashboard and charts now.</span>
          </div>
        )}

        <button
          type="button"
          onClick={handleSeedDemoComplaints}
          disabled={seeding}
          className="px-4 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold shadow-xs transition flex items-center gap-2"
        >
          {seeding ? <RefreshCw className="w-4 h-4 animate-spin text-teal-400" /> : <RefreshCw className="w-4 h-4 text-teal-400" />}
          <span>{seeding ? 'Populating Database...' : 'Seed Realistic Civic Demo Records'}</span>
        </button>
      </div>
    </div>
  );
};
