import React from 'react';
import {
  PieChart,
  BrainCircuit,
  Search,
  ShieldAlert,
  FileText,
  BarChart3,
} from 'lucide-react';

export const SolutionSection: React.FC = () => {
  const capabilities = [
    {
      icon: BarChart3,
      title: "Authoritative Financial Overview",
      description:
        "Deterministic reconciliation of total income, posted expenditures, and net surplus. Excludes internal account transfers to prevent double-counting of liquidity.",
    },
    {
      icon: BrainCircuit,
      title: "AI-Powered Financial Questions",
      description:
        "Ask plain-English questions about spending habits or vendor histories. The assistant executes schema-constrained SQL against IBM Db2 and quotes verified transaction IDs in its response.",
    },
    {
      icon: Search,
      title: "Db2 Native Semantic Search",
      description:
        "Find expenses by concept rather than exact keyword matches. Searches through 384-dimensional vector embeddings stored natively in IBM Db2 tables.",
    },
    {
      icon: ShieldAlert,
      title: "Explainable Anomaly Detection",
      description:
        "Flags statistical deviations against historical category averages with transparent context (e.g. 2.4x baseline). Highlights outliers for user review without assuming fraud.",
    },
    {
      icon: PieChart,
      title: "Transaction Intelligence",
      description:
        "Normalize irregular merchant strings, resolve counterparty identities, and maintain an immutable ledger with provenance tracking for every posted charge.",
    },
    {
      icon: FileText,
      title: "Auditable Financial Reports",
      description:
        "Generate comprehensive financial health summaries, savings rate analysis, and recurring cost forecasts backed by reproducible database aggregations.",
    },
  ];

  return (
    <section id="features" className="py-20 lg:py-28 border-t border-slate-200/80 dark:border-slate-800/80">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="max-w-3xl mx-auto text-center space-y-4 mb-16">
          <span className="text-xs font-semibold uppercase tracking-widest text-slate-500 dark:text-slate-400">
            Core Capabilities
          </span>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight text-slate-950 dark:text-white">
            Turn financial activity into understanding.
          </h2>
          <p className="text-base sm:text-lg text-slate-600 dark:text-slate-300 leading-relaxed">
            By connecting an enterprise database engine directly to modern language models, FinSight AI eliminates financial guesswork and provides explainable answers.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 lg:gap-8">
          {capabilities.map((cap, idx) => {
            const Icon = cap.icon;
            return (
              <div
                key={idx}
                className="p-6 rounded-xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-950 hover:border-slate-300 dark:hover:border-slate-700 transition-colors space-y-3.5 shadow-xs"
              >
                <div className="w-10 h-10 rounded-lg bg-slate-100 dark:bg-slate-900 flex items-center justify-center text-slate-800 dark:text-slate-200">
                  <Icon className="w-5 h-5" />
                </div>
                <h3 className="text-base font-semibold text-slate-900 dark:text-white">
                  {cap.title}
                </h3>
                <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
                  {cap.description}
                </p>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
};
