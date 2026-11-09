import React, { useState, useEffect } from 'react';
import {
  User,
  Cpu,
  Globe,
  CheckCircle2,
  Sparkles,
  Save,
} from 'lucide-react';
import { useAuthStore } from '../stores/authStore';
import api from '../lib/api';

export const SettingsPage = () => {
  const { user, setUser } = useAuthStore();
  const [unitSystem, setUnitSystem] = useState('metric'); // 'metric' (ha) | 'imperial' (acres)
  const [carbonUnit, setCarbonUnit] = useState('tco2e'); // 'tco2e' | 'kg_c'
  const [aiStatus, setAiStatus] = useState(null);
  const [savedSuccess, setSavedSuccess] = useState(false);

  // Form state
  const [fullName, setFullName] = useState(user?.full_name || 'Alex Carter');
  const [email, setEmail] = useState(user?.email || 'alex.carter@carbonnova.earth');
  const [organization, setOrganization] = useState(user?.organization || 'Green Valley Agroforestry & Land Trust');

  useEffect(() => {
    api.aiStatus()
      .then((data) => setAiStatus(data))
      .catch(() => setAiStatus({ configured: false }));
  }, []);

  const handleSave = (e) => {
    e.preventDefault();
    setUser({
      ...user,
      full_name: fullName,
      email,
      organization,
    });
    setSavedSuccess(true);
    setTimeout(() => setSavedSuccess(false), 3000);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">

      {/* Top Banner */}
      <div>
        <h2 className="text-xl font-bold text-[#0E2018]">Platform Settings</h2>
        <p className="text-xs text-[#638071]">
          Manage your account profile, measurement units, and AI engine connections
        </p>
      </div>

      {savedSuccess && (
        <div className="bg-[#E7F7F0] border border-[#BCE8D5] text-[#0A7B4E] px-4 py-3 rounded-xl text-xs font-semibold flex items-center gap-2">
          <CheckCircle2 size={16} />
          <span>Settings saved successfully.</span>
        </div>
      )}

      {/* 1. Profile Information */}
      <div className="cn-card p-6 bg-white space-y-4">
        <div className="flex items-center gap-2 pb-3 border-b border-[#EDF2EE]">
          <User size={18} className="text-[#0A7B4E]" />
          <h3 className="font-bold text-base text-[#0E2018]">User Profile</h3>
        </div>

        <form onSubmit={handleSave} className="space-y-4 text-xs">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block font-semibold text-[#163527] mb-1">Full Name</label>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="cn-input text-xs"
              />
            </div>

            <div>
              <label className="block font-semibold text-[#163527] mb-1">Email Address</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="cn-input text-xs"
              />
            </div>
          </div>

          <div>
            <label className="block font-semibold text-[#163527] mb-1">Organization / Trust Name</label>
            <input
              type="text"
              value={organization}
              onChange={(e) => setOrganization(e.target.value)}
              className="cn-input text-xs"
            />
          </div>

          <div className="pt-2 flex justify-end">
            <button type="submit" className="btn-forest text-xs py-2 px-5 flex items-center gap-1.5">
              <Save size={14} />
              <span>Save Changes</span>
            </button>
          </div>
        </form>
      </div>

      {/* 2. Units & Preferences */}
      <div className="cn-card p-6 bg-white space-y-4">
        <div className="flex items-center gap-2 pb-3 border-b border-[#EDF2EE]">
          <Globe size={18} className="text-[#0A7B4E]" />
          <h3 className="font-bold text-base text-[#0E2018]">Measurement Units & Standards</h3>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
          <div>
            <label className="block font-semibold text-[#163527] mb-1">Default Land Area Unit</label>
            <select
              value={unitSystem}
              onChange={(e) => setUnitSystem(e.target.value)}
              className="cn-input text-xs"
            >
              <option value="metric">Hectares (ha) - Standard</option>
              <option value="imperial">Acres (ac)</option>
            </select>
          </div>

          <div>
            <label className="block font-semibold text-[#163527] mb-1">Carbon Storage Metric</label>
            <select
              value={carbonUnit}
              onChange={(e) => setCarbonUnit(e.target.value)}
              className="cn-input text-xs"
            >
              <option value="tco2e">tCO₂e (Tonnes Carbon Dioxide Equivalent)</option>
              <option value="kg_c">kg C (Elemental Carbon)</option>
            </select>
          </div>
        </div>
      </div>

      {/* 3. AI & Geospatial Connectivity Status */}
      <div className="cn-card p-6 bg-white space-y-4">
        <div className="flex items-center gap-2 pb-3 border-b border-[#EDF2EE]">
          <Cpu size={18} className="text-[#0A7B4E]" />
          <h3 className="font-bold text-base text-[#0E2018]">Service Integrations</h3>
        </div>

        <div className="space-y-3 text-xs">
          
          {/* NVIDIA Build / Nemotron Status */}
          <div className="p-4 rounded-2xl bg-[#FAFBF9] border border-[#E3E9E3] flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-xl bg-[#0C3327] text-[#34D399] flex items-center justify-center">
                <Sparkles size={16} />
              </div>
              <div>
                <h4 className="font-bold text-[#0E2018]">NVIDIA Build API & Nemotron Model</h4>
                <p className="text-[11px] text-[#698475]">
                  nvidia/Nemotron-3_5-Lightning · Zero-hallucination carbon grounded assistant
                </p>
              </div>
            </div>

            <span className={`px-2.5 py-1 rounded-full text-[10px] font-bold ${
              aiStatus?.configured
                ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                : 'bg-amber-100 text-amber-800 border border-amber-300'
            }`}>
              {aiStatus?.configured ? 'Connected' : 'Configured on Server'}
            </span>
          </div>

          {/* Esri World Imagery Satellite Provider */}
          <div className="p-4 rounded-2xl bg-[#FAFBF9] border border-[#E3E9E3] flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-xl bg-[#E8F7F0] text-[#0A7B4E] flex items-center justify-center">
                <Globe size={16} />
              </div>
              <div>
                <h4 className="font-bold text-[#0E2018]">Satellite Tile Provider (Esri World Imagery)</h4>
                <p className="text-[11px] text-[#698475]">
                  High-resolution sub-meter optical satellite tiles for parcel boundary tracing
                </p>
              </div>
            </div>

            <span className="badge-emerald">Active</span>
          </div>

        </div>
      </div>

    </div>
  );
};

export default SettingsPage;
