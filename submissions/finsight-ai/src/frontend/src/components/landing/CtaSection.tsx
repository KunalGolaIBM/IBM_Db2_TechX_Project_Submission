import React from 'react';
import { ArrowRight, ShieldCheck, Database } from 'lucide-react';

interface CtaSectionProps {
  onNavigate: (route: string) => void;
}

export const CtaSection: React.FC<CtaSectionProps> = ({ onNavigate }) => {
  return (
    <section className="py-20 lg:py-28 border-t border-slate-200/80 dark:border-slate-800/80 bg-slate-50/50 dark:bg-slate-900/40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="max-w-4xl mx-auto text-center space-y-6">
          <span className="text-xs font-semibold uppercase tracking-widest text-slate-500 dark:text-slate-400">
            Start Exploring
          </span>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-tightest text-slate-950 dark:text-white">
            Experience database-first financial intelligence.
          </h2>
          <p className="text-base sm:text-lg text-slate-600 dark:text-slate-300 leading-relaxed max-w-2xl mx-auto">
            Explore 208 verified transactions, test natural-language financial questions, and see explainable anomaly detection in action.
          </p>

          <div className="pt-4 flex flex-col sm:flex-row items-center justify-center gap-4">
            <button
              onClick={() => onNavigate('/register')}
              className="w-full sm:w-auto inline-flex items-center justify-center space-x-2 px-7 py-3.5 rounded-lg bg-slate-900 text-white dark:bg-white dark:text-slate-950 font-medium text-sm hover:bg-slate-800 dark:hover:bg-slate-100 shadow-sm transition-all"
            >
              <span>Get Started</span>
              <ArrowRight className="w-4 h-4" />
            </button>
            <button
              onClick={() => onNavigate('/login')}
              className="w-full sm:w-auto inline-flex items-center justify-center px-7 py-3.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white/80 dark:bg-slate-900/80 font-medium text-sm text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
            >
              Sign In to Workspace
            </button>
          </div>

          <div className="pt-6 flex flex-wrap items-center justify-center gap-6 text-xs text-slate-500">
            <div className="flex items-center space-x-1.5">
              <ShieldCheck className="w-4 h-4 text-emerald-500" />
              <span>Argon2id Session Authentication</span>
            </div>
            <div className="flex items-center space-x-1.5">
              <Database className="w-4 h-4 text-sky-500" />
              <span>IBM Db2 Community Edition Backend</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
