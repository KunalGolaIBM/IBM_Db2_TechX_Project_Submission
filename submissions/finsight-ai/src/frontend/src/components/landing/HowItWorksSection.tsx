import React from 'react';
import { UploadCloud, CheckCheck, Database, Brain, Sparkles } from 'lucide-react';

export const HowItWorksSection: React.FC = () => {
  const steps = [
    {
      step: "01",
      icon: UploadCloud,
      title: "Financial Data Ingestion",
      description: "Bank statements and transaction feeds are imported into FinSight AI.",
    },
    {
      step: "02",
      icon: CheckCheck,
      title: "Mathematical Validation",
      description: "High-performance Rust gateway sanitizes data and validates ledger balances.",
    },
    {
      step: "03",
      icon: Database,
      title: "IBM Db2 Persistence",
      description: "Records stored in ACID relational tables and native 384-dim vector stores.",
    },
    {
      step: "04",
      icon: Brain,
      title: "LangChain AI Intelligence",
      description: "FastAPI service translates user questions into targeted vector & SQL queries.",
    },
    {
      step: "05",
      icon: Sparkles,
      title: "Explainable Insights",
      description: "Clear answers delivered with verified transaction proof and interactive charts.",
    },
  ];

  return (
    <section id="how-it-works" className="py-20 lg:py-28 border-t border-slate-200/80 dark:border-slate-800/80">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="max-w-3xl mx-auto text-center space-y-4 mb-16">
          <span className="text-xs font-semibold uppercase tracking-widest text-slate-500 dark:text-slate-400">
            End-to-End Pipeline
          </span>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight text-slate-950 dark:text-white">
            How FinSight works
          </h2>
          <p className="text-base sm:text-lg text-slate-600 dark:text-slate-300 leading-relaxed">
            From raw transaction records to verified financial answers in five transparent steps.
          </p>
        </div>

        {/* Desktop Pipeline Flow */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4 relative">
          {steps.map((item, idx) => {
            const Icon = item.icon;
            return (
              <div
                key={idx}
                className="p-5 rounded-xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-950 space-y-3 relative shadow-xs flex flex-col justify-between"
              >
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-bold text-slate-400">
                      {item.step}
                    </span>
                    <div className="w-8 h-8 rounded-md bg-slate-100 dark:bg-slate-900 flex items-center justify-center text-slate-700 dark:text-slate-300">
                      <Icon className="w-4 h-4" />
                    </div>
                  </div>
                  <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
                    {item.title}
                  </h3>
                  <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                    {item.description}
                  </p>
                </div>
              </div>
            );
          })}
        </div>

        {/* Technical Architecture Summary pill */}
        <div className="mt-12 p-4 rounded-xl border border-slate-200/60 dark:border-slate-800/60 bg-slate-50/60 dark:bg-slate-900/30 max-w-3xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-slate-600 dark:text-slate-400">
          <div className="flex items-center space-x-2">
            <span className="font-semibold text-slate-900 dark:text-white">Under the hood:</span>
            <span>React + TypeScript · Rust Axum Gateway · Python FastAPI · IBM Db2 Community Edition</span>
          </div>
          <span className="font-mono text-slate-400 text-[11px]">Strict Tenant Boundary</span>
        </div>
      </div>
    </section>
  );
};
