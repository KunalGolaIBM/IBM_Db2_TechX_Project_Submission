import React from 'react';
import { Link } from 'react-router-dom';
import { 
  ShieldAlert, ShieldCheck, Users, Eye, Clock, 
  HeartHandshake, ChevronRight, CheckCircle2, Lock, Cpu, Sparkles 
} from 'lucide-react';
import { AndroidDownloadSection } from '../components/AndroidDownloadSection';

export const LandingPage: React.FC = () => {
  return (
    <div className="space-y-16 py-8">
      
      {/* Hero Section */}
      <section className="relative overflow-hidden pt-8 pb-12 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
        <div className="text-center max-w-3xl mx-auto space-y-6">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-teal-500/10 text-teal-700 dark:text-teal-400 border border-teal-500/20 text-xs font-semibold tracking-wide uppercase">
            <Sparkles className="w-3.5 h-3.5 text-teal-500" />
            Civic Protection Platform • Powered by IBM Db2 & FastAPI
          </div>
          
          <h1 className="text-4xl sm:text-5xl md:text-6xl font-extrabold text-slate-900 tracking-tight leading-tight">
            Neighbourhood Safety <br />
            <span className="text-teal-600 bg-gradient-to-r from-teal-600 to-cyan-600 bg-clip-text text-transparent">
              Intelligence Network
            </span>
          </h1>

          <p className="text-lg text-slate-600 max-w-2xl mx-auto leading-relaxed">
            A privacy-first, community-driven civic defense network connecting residents, 
            trusted family contacts, verified local responders, and municipal coordinators with 
            real-time incident triage, automated SOS coordination, and AI-assisted safety workflows.
          </p>

          <div className="flex flex-wrap items-center justify-center gap-4 pt-2">
            <Link
              to="/auth?mode=register"
              className="bg-slate-900 hover:bg-slate-800 text-white font-semibold px-6 py-3.5 rounded-xl shadow-lg transition-all hover:scale-[1.02] flex items-center gap-2"
            >
              Join Safety Network
              <ChevronRight className="w-4 h-4 text-teal-400" />
            </Link>
            
            <a
              href="#download-android-app"
              className="bg-teal-50 text-teal-800 hover:bg-teal-100 font-semibold px-6 py-3.5 rounded-xl border border-teal-200 transition flex items-center gap-2"
            >
              Get Android Companion
            </a>
          </div>

          {/* Quick Metrics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-10 text-left">
            <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
              <span className="text-2xl font-bold text-slate-900">&lt; 120s</span>
              <p className="text-xs text-slate-500 mt-0.5">Average Responder Acknowledge</p>
            </div>
            <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
              <span className="text-2xl font-bold text-teal-600">100%</span>
              <p className="text-xs text-slate-500 mt-0.5">Auditable Incident Ledger</p>
            </div>
            <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
              <span className="text-2xl font-bold text-slate-900">Zero PII</span>
              <p className="text-xs text-slate-500 mt-0.5">No Public Location Exposure</p>
            </div>
            <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
              <span className="text-2xl font-bold text-teal-600">Cross-Sync</span>
              <p className="text-xs text-slate-500 mt-0.5">Unified Web + Android Core</p>
            </div>
          </div>

        </div>
      </section>

      {/* How It Works */}
      <section id="how-it-works" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="text-center max-w-2xl mx-auto mb-12">
          <h2 className="text-3xl font-bold text-slate-900">The Complete Incident Lifecycle</h2>
          <p className="text-slate-600 text-sm mt-2">
            Every distress signal follows a strict, accountable, human-in-the-loop civic protocol.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          
          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm relative">
            <div className="w-8 h-8 rounded-full bg-red-100 text-red-600 font-bold flex items-center justify-center text-sm mb-3">1</div>
            <h3 className="font-semibold text-slate-900 text-base">Distress / Report</h3>
            <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">
              Resident triggers SOS or logs a hazard with optional location breadcrumbs.
            </p>
          </div>

          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm relative">
            <div className="w-8 h-8 rounded-full bg-teal-100 text-teal-700 font-bold flex items-center justify-center text-sm mb-3">2</div>
            <h3 className="font-semibold text-slate-900 text-base">Backend Triage</h3>
            <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">
              FastAPI backend validates authorization, notifies trusted contacts, and runs AI triage intake.
            </p>
          </div>

          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm relative">
            <div className="w-8 h-8 rounded-full bg-blue-100 text-blue-700 font-bold flex items-center justify-center text-sm mb-3">3</div>
            <h3 className="font-semibold text-slate-900 text-base">Responder Claim</h3>
            <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">
              Verified local patrol or medical volunteer acknowledges and claims the dispatch.
            </p>
          </div>

          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm relative">
            <div className="w-8 h-8 rounded-full bg-amber-100 text-amber-700 font-bold flex items-center justify-center text-sm mb-3">4</div>
            <h3 className="font-semibold text-slate-900 text-base">Live Coordination</h3>
            <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">
              Responder logs en route & on-scene arrivals. Both Web & Android apps update in sync.
            </p>
          </div>

          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm relative">
            <div className="w-8 h-8 rounded-full bg-emerald-100 text-emerald-700 font-bold flex items-center justify-center text-sm mb-3">5</div>
            <h3 className="font-semibold text-slate-900 text-base">Resolution Audit</h3>
            <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">
              Incident is securely closed with detailed timestamped notes and municipal archival.
            </p>
          </div>

        </div>
      </section>

      {/* Safety Pillars */}
      <section id="safety-pillars" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="text-center max-w-2xl mx-auto mb-12">
          <h2 className="text-3xl font-bold text-slate-900">Tailored Safety Workflows</h2>
          <p className="text-slate-600 text-sm mt-2">
            Civic assistance specialized for vulnerable community members.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          
          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm hover:border-teal-500/50 transition">
            <div className="w-12 h-12 rounded-xl bg-red-100 text-red-600 flex items-center justify-center mb-4">
              <ShieldAlert className="w-6 h-6" />
            </div>
            <h3 className="text-lg font-bold text-slate-900">One-Tap Emergency SOS</h3>
            <p className="text-xs text-slate-600 mt-2 leading-relaxed">
              Broadcasts immediate P1 distress alerts to designated family contacts and on-duty verified responders within 2km with exact coordinates.
            </p>
            <ul className="mt-4 space-y-1.5 text-xs text-slate-500">
              <li className="flex items-center gap-1.5"><CheckCircle2 className="w-3.5 h-3.5 text-teal-600" /> False alarm cancellation safeguards</li>
              <li className="flex items-center gap-1.5"><CheckCircle2 className="w-3.5 h-3.5 text-teal-600" /> Emergency medical note visibility</li>
            </ul>
          </div>

          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm hover:border-teal-500/50 transition">
            <div className="w-12 h-12 rounded-xl bg-teal-100 text-teal-700 flex items-center justify-center mb-4">
              <Eye className="w-6 h-6" />
            </div>
            <h3 className="text-lg font-bold text-slate-900">Safe Transit for Women</h3>
            <p className="text-xs text-slate-600 mt-2 leading-relaxed">
              Night corridor companion protocol with active breadcrumbs shared solely with trusted guardians and community drive-by patrols.
            </p>
            <ul className="mt-4 space-y-1.5 text-xs text-slate-500">
              <li className="flex items-center gap-1.5"><CheckCircle2 className="w-3.5 h-3.5 text-teal-600" /> Automated stationary prompt check</li>
              <li className="flex items-center gap-1.5"><CheckCircle2 className="w-3.5 h-3.5 text-teal-600" /> Dark alley & unlit hazard rerouting</li>
            </ul>
          </div>

          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm hover:border-teal-500/50 transition">
            <div className="w-12 h-12 rounded-xl bg-blue-100 text-blue-700 flex items-center justify-center mb-4">
              <Users className="w-6 h-6" />
            </div>
            <h3 className="text-lg font-bold text-slate-900">Child Journey Waypoints</h3>
            <p className="text-xs text-slate-600 mt-2 leading-relaxed">
              Monitors school bus routes and daily commutes with expected arrival windows and guardian check-in checkpoints.
            </p>
            <ul className="mt-4 space-y-1.5 text-xs text-slate-500">
              <li className="flex items-center gap-1.5"><CheckCircle2 className="w-3.5 h-3.5 text-teal-600" /> Overdue +15m escalation tree</li>
              <li className="flex items-center gap-1.5"><CheckCircle2 className="w-3.5 h-3.5 text-teal-600" /> Waypoint check-in verification</li>
            </ul>
          </div>

          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm hover:border-teal-500/50 transition">
            <div className="w-12 h-12 rounded-xl bg-amber-100 text-amber-700 flex items-center justify-center mb-4">
              <HeartHandshake className="w-6 h-6" />
            </div>
            <h3 className="text-lg font-bold text-slate-900">Senior Citizen Welfare</h3>
            <p className="text-xs text-slate-600 mt-2 leading-relaxed">
              Scheduled morning and evening check-ins, medication assistance requests, and physical volunteer check-in visits.
            </p>
            <ul className="mt-4 space-y-1.5 text-xs text-slate-500">
              <li className="flex items-center gap-1.5"><CheckCircle2 className="w-3.5 h-3.5 text-teal-600" /> Missed check-in auto-prompt</li>
              <li className="flex items-center gap-1.5"><CheckCircle2 className="w-3.5 h-3.5 text-teal-600" /> Prescription & grocery assistance</li>
            </ul>
          </div>

          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm hover:border-teal-500/50 transition">
            <div className="w-12 h-12 rounded-xl bg-purple-100 text-purple-700 flex items-center justify-center mb-4">
              <Clock className="w-6 h-6" />
            </div>
            <h3 className="text-lg font-bold text-slate-900">Verified Civic Responders</h3>
            <p className="text-xs text-slate-600 mt-2 leading-relaxed">
              Certified community patrol members and medical first responders with background checks, badges, and performance ratings.
            </p>
            <ul className="mt-4 space-y-1.5 text-xs text-slate-500">
              <li className="flex items-center gap-1.5"><CheckCircle2 className="w-3.5 h-3.5 text-teal-600" /> Availability toggle & dispatch queue</li>
              <li className="flex items-center gap-1.5"><CheckCircle2 className="w-3.5 h-3.5 text-teal-600" /> Admin background accreditation</li>
            </ul>
          </div>

          <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm hover:border-teal-500/50 transition">
            <div className="w-12 h-12 rounded-xl bg-cyan-100 text-cyan-700 flex items-center justify-center mb-4">
              <Cpu className="w-6 h-6" />
            </div>
            <h3 className="text-lg font-bold text-slate-900">AI Safety Intelligence</h3>
            <p className="text-xs text-slate-600 mt-2 leading-relaxed">
              Haystack BM25 knowledge retrieval and bounded triage agents providing instant preliminary triage and safety checklists.
            </p>
            <ul className="mt-4 space-y-1.5 text-xs text-slate-500">
              <li className="flex items-center gap-1.5"><CheckCircle2 className="w-3.5 h-3.5 text-teal-600" /> Official municipal SOP citations</li>
              <li className="flex items-center gap-1.5"><CheckCircle2 className="w-3.5 h-3.5 text-teal-600" /> Strictly advisory, human-supervised</li>
            </ul>
          </div>

        </div>
      </section>

      {/* Embedded Android Download Section */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <AndroidDownloadSection />
      </div>

      {/* Privacy & Zero-Trust Architecture */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-slate-900 text-white rounded-3xl p-8 md:p-12 border border-slate-800">
          <div className="max-w-3xl space-y-4">
            <div className="inline-flex items-center gap-2 text-xs font-semibold text-teal-400 bg-teal-500/10 px-3 py-1 rounded-full border border-teal-500/30">
              <Lock className="w-3.5 h-3.5" />
              Privacy-by-Design Commitment
            </div>
            <h2 className="text-2xl md:text-3xl font-bold">
              Built to Protect Citizens, Not Exploit Their Data
            </h2>
            <p className="text-slate-300 text-sm leading-relaxed">
              Civic safety networks handle delicate personal information. Our architecture guarantees:
            </p>
            <div className="grid sm:grid-cols-2 gap-3 pt-2 text-xs text-slate-300">
              <div className="flex items-start gap-2 bg-slate-800/60 p-3 rounded-xl border border-slate-700">
                <CheckCircle2 className="w-4 h-4 text-teal-400 shrink-0 mt-0.5" />
                <span><strong>No Public Maps:</strong> Individual live locations and private distress reports are never visible to the public.</span>
              </div>
              <div className="flex items-start gap-2 bg-slate-800/60 p-3 rounded-xl border border-slate-700">
                <CheckCircle2 className="w-4 h-4 text-teal-400 shrink-0 mt-0.5" />
                <span><strong>Role-Based Access:</strong> Child data is restricted strictly to verified guardians and responding patrol officers.</span>
              </div>
              <div className="flex items-start gap-2 bg-slate-800/60 p-3 rounded-xl border border-slate-700">
                <CheckCircle2 className="w-4 h-4 text-teal-400 shrink-0 mt-0.5" />
                <span><strong>No Autonomous Dispatch:</strong> AI assistants never deploy units or accuse individuals; human responders retain full control.</span>
              </div>
              <div className="flex items-start gap-2 bg-slate-800/60 p-3 rounded-xl border border-slate-700">
                <CheckCircle2 className="w-4 h-4 text-teal-400 shrink-0 mt-0.5" />
                <span><strong>IBM Db2 Enterprise Security:</strong> Parameterized queries and encrypted transactions for robust civic defense.</span>
              </div>
            </div>
          </div>
        </div>
      </section>

    </div>
  );
};
