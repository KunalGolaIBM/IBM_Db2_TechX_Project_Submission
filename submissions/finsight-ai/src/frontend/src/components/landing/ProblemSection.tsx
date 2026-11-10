import React from 'react';
import { HelpCircle, FileSpreadsheet, AlertTriangle } from 'lucide-react';

export const ProblemSection: React.FC = () => {
  return (
    <section id="problem" className="py-20 lg:py-28 border-t border-slate-200/80 dark:border-slate-800/80 bg-slate-50/50 dark:bg-slate-900/20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="max-w-3xl mx-auto text-center space-y-4 mb-16">
          <span className="text-xs font-semibold uppercase tracking-widest text-slate-500 dark:text-slate-400">
            The Financial Data Challenge
          </span>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight text-slate-950 dark:text-white">
            More transactions. Less clarity.
          </h2>
          <p className="text-base sm:text-lg text-slate-600 dark:text-slate-300 leading-relaxed">
            Modern banking provides an endless stream of digital transactions, yet understanding what actually happened to your capital remains surprisingly difficult.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 lg:gap-8">
          {/* Problem 1 */}
          <div className="p-6 rounded-xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-950 space-y-3.5 shadow-xs">
            <div className="w-10 h-10 rounded-lg bg-slate-100 dark:bg-slate-900 flex items-center justify-center text-slate-700 dark:text-slate-300">
              <FileSpreadsheet className="w-5 h-5" />
            </div>
            <h3 className="text-base font-semibold text-slate-900 dark:text-white">
              Fragmented Transaction Ledgers
            </h3>
            <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
              Cryptic merchant descriptions ("UPI/42819/POS*549") obscure genuine vendors. Category tagging fails on split purchases, leaving spending patterns hidden in static statements.
            </p>
          </div>

          {/* Problem 2 */}
          <div className="p-6 rounded-xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-950 space-y-3.5 shadow-xs">
            <div className="w-10 h-10 rounded-lg bg-slate-100 dark:bg-slate-900 flex items-center justify-center text-slate-700 dark:text-slate-300">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <h3 className="text-base font-semibold text-slate-900 dark:text-white">
              Unexplained Anomaly Alerts
            </h3>
            <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
              Traditional banking alerts either flood users with false alarms or stay silent when recurring subscriptions silently inflate. When flags occur, no statistical explanation is provided.
            </p>
          </div>

          {/* Problem 3 */}
          <div className="p-6 rounded-xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-950 space-y-3.5 shadow-xs">
            <div className="w-10 h-10 rounded-lg bg-slate-100 dark:bg-slate-900 flex items-center justify-center text-slate-700 dark:text-slate-300">
              <HelpCircle className="w-5 h-5" />
            </div>
            <h3 className="text-base font-semibold text-slate-900 dark:text-white">
              AI Hallucinations with Personal Finances
            </h3>
            <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
              Generic conversational chatbots guess numbers and invent totals without database grounding. Financial intelligence requires deterministic calculations tied to immutable ledger rows.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
};
