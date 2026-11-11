import React from 'react';
import { Shield, PhoneCall, Lock, Heart, Database, Code2 } from 'lucide-react';

export const Footer: React.FC = () => {
  return (
    <footer id="helplines" className="bg-slate-950 text-slate-400 border-t border-slate-800 text-sm mt-auto">
      {/* Crisis Emergency Strip */}
      <div className="bg-red-950/40 border-b border-red-900/30 py-3 px-4">
        <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-4 text-xs">
          <div className="flex items-center gap-2 text-red-300 font-semibold">
            <PhoneCall className="w-4 h-4 text-red-400 animate-pulse" />
            National Emergency Quick Helplines:
          </div>
          <div className="flex flex-wrap items-center gap-4 text-slate-300">
            <span>Unified Emergency: <strong className="text-white">112</strong></span>
            <span>Police: <strong className="text-white">100</strong></span>
            <span>Women in Distress: <strong className="text-white">1091</strong></span>
            <span>Childline: <strong className="text-white">1098</strong></span>
            <span>Senior Citizen Line: <strong className="text-white">14567</strong></span>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          
          <div className="md:col-span-2 space-y-4">
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-lg bg-teal-600/30 border border-teal-500/40 p-1.5 flex items-center justify-center">
                <Shield className="w-5 h-5 text-teal-400" />
              </div>
              <span className="font-bold text-lg text-white">Neighbourhood Safety Intelligence</span>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed max-w-md">
              A privacy-first, community-driven civic safety network connecting residents, vulnerable citizens, 
              trusted family contacts, verified volunteer responders, and municipal authorities with real-time 
              incident triage and AI assistance.
            </p>
            <div className="flex items-center gap-4 text-xs text-slate-400">
              <span className="flex items-center gap-1.5 text-teal-400">
                <Lock className="w-3.5 h-3.5" /> Zero Public PII Leaks
              </span>
              <span className="flex items-center gap-1.5 text-teal-400">
                <Database className="w-3.5 h-3.5" /> IBM Db2 Enterprise Ready
              </span>
            </div>
          </div>

          <div>
            <h4 className="font-semibold text-white text-xs uppercase tracking-wider mb-3">Core Modules</h4>
            <ul className="space-y-2 text-xs">
              <li><a href="#safety-pillars" className="hover:text-teal-400 transition">Emergency SOS Protocol</a></li>
              <li><a href="#safety-pillars" className="hover:text-teal-400 transition">Safe Transit for Women</a></li>
              <li><a href="#safety-pillars" className="hover:text-teal-400 transition">Child Journey Tracking</a></li>
              <li><a href="#safety-pillars" className="hover:text-teal-400 transition">Senior Citizen Care</a></li>
              <li><a href="#safety-pillars" className="hover:text-teal-400 transition">Civic Hazard Registry</a></li>
            </ul>
          </div>

          <div>
            <h4 className="font-semibold text-white text-xs uppercase tracking-wider mb-3">Technical Architecture</h4>
            <ul className="space-y-2 text-xs">
              <li className="flex items-center gap-1.5"><Code2 className="w-3.5 h-3.5 text-teal-400" /> Python FastAPI Shared Core</li>
              <li className="flex items-center gap-1.5"><Database className="w-3.5 h-3.5 text-teal-400" /> IBM Db2 / SQLite Adapters</li>
              <li className="flex items-center gap-1.5"><Shield className="w-3.5 h-3.5 text-teal-400" /> Haystack BM25 & Triage Agents</li>
              <li className="flex items-center gap-1.5"><Heart className="w-3.5 h-3.5 text-teal-400" /> Jetpack Compose Native App</li>
            </ul>
            <div className="mt-4 pt-4 border-t border-slate-800 text-[11px] text-slate-500">
              Built for IBM Db2 TechX Project Submission
            </div>
          </div>

        </div>

        <div className="mt-8 pt-6 border-t border-slate-800 text-xs text-center text-slate-500">
          © {new Date().getFullYear()} Neighbourhood Safety Intelligence Network. All Rights Reserved. Civic Technology Initiative.
        </div>
      </div>
    </footer>
  );
};
