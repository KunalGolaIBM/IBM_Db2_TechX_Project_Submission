import React from 'react';
import { ArrowRight, Sparkles, Shield, Database, Search, AlertCircle, CheckCircle2 } from 'lucide-react';

interface HeroSectionProps {
  onNavigate: (route: string) => void;
}

export const HeroSection: React.FC<HeroSectionProps> = ({ onNavigate }) => {
  const scrollToFeatures = (e: React.MouseEvent) => {
    e.preventDefault();
    const el = document.getElementById('features');
    if (el) el.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <section id="product" className="relative pt-12 pb-20 md:pt-20 md:pb-32 overflow-hidden">
      {/* Background ambient lighting - subtle, minimalist Apple-style */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-7xl h-96 bg-gradient-to-b from-slate-100/60 to-transparent dark:from-slate-900/30 dark:to-transparent pointer-events-none -z-10" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="max-w-3xl mx-auto text-center space-y-6">
          {/* Badge */}
          <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full text-xs font-medium bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-slate-700 shadow-xs">
            <span className="w-1.5 h-1.5 rounded-full bg-sky-500 animate-pulse"></span>
            <span>IBM Db2Hack 2026 Submission</span>
            <span className="text-slate-400 dark:text-slate-500">•</span>
            <span className="text-slate-600 dark:text-slate-400">Database-First Financial AI</span>
          </div>

          {/* Headline */}
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tightest text-slate-950 dark:text-white leading-[1.08]">
            Your money has a story.<br className="hidden sm:inline" /> Understand it.
          </h1>

          {/* Supporting Text */}
          <p className="text-lg sm:text-xl text-slate-600 dark:text-slate-300 font-normal leading-relaxed max-w-2xl mx-auto">
            FinSight AI turns raw financial transaction records into clear, explainable financial intelligence. Grounded directly in authoritative IBM Db2 database records with mathematical proof.
          </p>

          {/* CTAs */}
          <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-3.5 sm:gap-4">
            <button
              onClick={() => onNavigate('/register')}
              className="w-full sm:w-auto inline-flex items-center justify-center space-x-2 px-6 py-3 rounded-lg bg-slate-900 text-white dark:bg-white dark:text-slate-950 font-medium text-sm hover:bg-slate-800 dark:hover:bg-slate-100 shadow-sm transition-all"
            >
              <span>Get Started</span>
              <ArrowRight className="w-4 h-4" />
            </button>
            <a
              href="#features"
              onClick={scrollToFeatures}
              className="w-full sm:w-auto inline-flex items-center justify-center px-6 py-3 rounded-lg border border-slate-300 dark:border-slate-700 bg-white/60 dark:bg-slate-900/60 font-medium text-sm text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
            >
              Explore Features
            </a>
          </div>

          <div className="pt-2 flex items-center justify-center space-x-6 text-xs text-slate-500">
            <div className="flex items-center space-x-1.5">
              <Shield className="w-3.5 h-3.5 text-slate-400" />
              <span>Strict Multi-Tenant Isolation</span>
            </div>
            <div className="flex items-center space-x-1.5">
              <Database className="w-3.5 h-3.5 text-slate-400" />
              <span>IBM Db2 Native Vector Store</span>
            </div>
          </div>
        </div>

        {/* Product Preview / Dashboard Mockup */}
        <div className="mt-14 sm:mt-18 max-w-5xl mx-auto">
          {/* Demo disclaimer banner */}
          <div className="flex items-center justify-between px-4 py-2 bg-slate-100/90 dark:bg-slate-900/90 border border-b-0 border-slate-200 dark:border-slate-800 rounded-t-xl text-xs text-slate-500">
            <div className="flex items-center space-x-2">
              <span className="w-2 h-2 rounded-full bg-amber-500"></span>
              <span className="font-medium text-slate-700 dark:text-slate-300">Illustrative Product Interface</span>
              <span className="hidden sm:inline text-slate-400">— Synthetic Demo Ledger (208 Records)</span>
            </div>
            <span className="font-mono text-[11px] text-slate-400">FINDB · Db2 12.1.5.0</span>
          </div>

          {/* Main Mockup Window */}
          <div className="rounded-b-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 shadow-xl overflow-hidden">
            {/* Mockup App Bar */}
            <div className="px-5 py-3.5 border-b border-slate-100 dark:border-slate-900 bg-slate-50/50 dark:bg-slate-900/40 flex items-center justify-between">
              <div className="flex items-center space-x-4">
                <div className="flex space-x-1.5">
                  <div className="w-3 h-3 rounded-full bg-slate-200 dark:bg-slate-700"></div>
                  <div className="w-3 h-3 rounded-full bg-slate-200 dark:bg-slate-700"></div>
                  <div className="w-3 h-3 rounded-full bg-slate-200 dark:bg-slate-700"></div>
                </div>
                <div className="hidden sm:flex items-center space-x-2 text-xs font-medium text-slate-500">
                  <span className="text-slate-900 dark:text-white font-semibold">FinSight Command Center</span>
                  <span>/</span>
                  <span>Portfolio Overview</span>
                </div>
              </div>
              <div className="flex items-center space-x-2.5">
                <div className="px-2.5 py-1 rounded bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-900 text-emerald-700 dark:text-emerald-400 text-xs font-mono font-medium">
                  Ledger: Verified ACID
                </div>
              </div>
            </div>

            {/* Mockup Dashboard Content */}
            <div className="p-5 sm:p-7 space-y-6">
              {/* Financial KPI Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="p-4 rounded-lg bg-slate-50 dark:bg-slate-900/60 border border-slate-100 dark:border-slate-800/80 space-y-1.5">
                  <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">Total Verified Inflow</span>
                  <div className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
                    ₹750,000.00
                  </div>
                  <div className="text-xs text-slate-500 flex items-center space-x-1">
                    <CheckCircle2 className="w-3 h-3 text-emerald-500" />
                    <span>6 Verified Salary Credits</span>
                  </div>
                </div>

                <div className="p-4 rounded-lg bg-slate-50 dark:bg-slate-900/60 border border-slate-100 dark:border-slate-800/80 space-y-1.5">
                  <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">Total Operating Outflow</span>
                  <div className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
                    ₹500,162.00
                  </div>
                  <div className="text-xs text-slate-500">
                    202 Posted Transactions
                  </div>
                </div>

                <div className="p-4 rounded-lg bg-slate-50 dark:bg-slate-900/60 border border-slate-100 dark:border-slate-800/80 space-y-1.5">
                  <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">Net Cash Surplus</span>
                  <div className="text-2xl font-bold tracking-tight text-emerald-600 dark:text-emerald-400">
                    +₹249,838.00
                  </div>
                  <div className="text-xs text-slate-500">
                    33.3% Net Savings Rate
                  </div>
                </div>
              </div>

              {/* Two Column Section in Mockup: AI Query + Semantic Search */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
                {/* AI Assistant Conversation preview */}
                <div className="lg:col-span-7 p-4 sm:p-5 rounded-lg border border-slate-200/80 dark:border-slate-800 bg-slate-50/40 dark:bg-slate-900/30 space-y-3.5">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <Sparkles className="w-4 h-4 text-sky-600 dark:text-sky-400" />
                      <span className="text-xs font-semibold uppercase tracking-wider text-slate-800 dark:text-slate-200">
                        Db2-Grounded Financial Intelligence
                      </span>
                    </div>
                    <span className="text-[11px] font-mono text-slate-400">Mode: Deterministic Proof</span>
                  </div>

                  <div className="space-y-2.5 text-xs">
                    {/* User Query */}
                    <div className="bg-white dark:bg-slate-900 p-2.5 rounded-md border border-slate-200/60 dark:border-slate-800 text-slate-800 dark:text-slate-200 font-medium">
                      "What is my verified monthly rent and cloud infrastructure spending?"
                    </div>
                    {/* Assistant Response */}
                    <div className="bg-slate-100 dark:bg-slate-800/60 p-3 rounded-md space-y-2 text-slate-700 dark:text-slate-300">
                      <p className="leading-relaxed">
                        Based on your posted transactions in Db2, you have made <strong className="text-slate-900 dark:text-white">6 monthly rent payments of ₹32,000.00</strong> (total ₹192,000.00). Cloud infrastructure spending across AWS and GCP totaled <strong className="text-slate-900 dark:text-white">₹59,840.00</strong> across 8 debits.
                      </p>
                      {/* Evidence Citations */}
                      <div className="pt-1.5 border-t border-slate-200 dark:border-slate-700/60 flex flex-wrap items-center gap-1.5 text-[11px]">
                        <span className="text-slate-400 font-medium">Evidence citations:</span>
                        <span className="px-1.5 py-0.5 rounded bg-sky-100 dark:bg-sky-950/80 text-sky-700 dark:text-sky-300 font-mono text-[10px]">
                          TX_0004
                        </span>
                        <span className="px-1.5 py-0.5 rounded bg-sky-100 dark:bg-sky-950/80 text-sky-700 dark:text-sky-300 font-mono text-[10px]">
                          TX_0038
                        </span>
                        <span className="px-1.5 py-0.5 rounded bg-sky-100 dark:bg-sky-950/80 text-sky-700 dark:text-sky-300 font-mono text-[10px]">
                          TX_0072
                        </span>
                        <span className="px-1.5 py-0.5 rounded bg-emerald-100 dark:bg-emerald-950/80 text-emerald-700 dark:text-emerald-300 font-mono text-[10px]">
                          SQL Verified: 100%
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Anomaly & Semantic Search snippet */}
                <div className="lg:col-span-5 space-y-4">
                  {/* Semantic Search box */}
                  <div className="p-3.5 rounded-lg border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900/60 space-y-2">
                    <div className="flex items-center space-x-2 text-xs font-semibold text-slate-800 dark:text-slate-200">
                      <Search className="w-3.5 h-3.5 text-slate-500" />
                      <span>Db2 Vector Semantic Search</span>
                    </div>
                    <div className="p-2 rounded bg-slate-50 dark:bg-slate-800/80 text-[11px] text-slate-600 dark:text-slate-400 font-mono">
                      "cabs and daily airport commute"
                    </div>
                    <div className="text-[11px] text-slate-500 flex items-center justify-between">
                      <span>Top match: Uber India (₹360.00)</span>
                      <span className="font-mono text-emerald-600 dark:text-emerald-400">86% similarity</span>
                    </div>
                  </div>

                  {/* Anomaly card */}
                  <div className="p-3.5 rounded-lg border border-amber-200/80 dark:border-amber-900/60 bg-amber-50/50 dark:bg-amber-950/20 space-y-1.5">
                    <div className="flex items-center space-x-1.5 text-xs font-semibold text-amber-900 dark:text-amber-200">
                      <AlertCircle className="w-3.5 h-3.5 text-amber-600" />
                      <span>Explainable Spending Outlier</span>
                    </div>
                    <p className="text-[11px] text-amber-800/90 dark:text-amber-300/80 leading-relaxed">
                      AWS billing increased by 2.8x compared to your 6-month historical baseline. Flagged for review, not assumed fraud.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
