import React from 'react';

interface FooterProps {
  onNavigate: (route: string) => void;
}

export const Footer: React.FC<FooterProps> = ({ onNavigate }) => {
  return (
    <footer className="border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/60 text-slate-600 dark:text-slate-400 text-sm transition-colors">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 lg:py-16">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8 lg:gap-12">
          {/* Col 1: Brand Info */}
          <div className="space-y-4 md:col-span-1">
            <div className="flex items-center space-x-2.5">
              <div className="w-8 h-8 rounded-lg bg-slate-900 dark:bg-white flex items-center justify-center text-white dark:text-slate-950 font-bold text-sm">
                F
              </div>
              <span className="font-semibold text-base text-slate-900 dark:text-white">FinSight AI</span>
            </div>
            <p className="text-xs leading-relaxed text-slate-500 dark:text-slate-400">
              Your money has a story. Understand it.
            </p>
            <div className="pt-2 flex items-center space-x-2 text-xs text-slate-500">
              <span className="inline-block w-2 h-2 rounded-full bg-emerald-500"></span>
              <span>IBM Db2Hack 2026 Project Entry</span>
            </div>
          </div>

          {/* Col 2: Product & Capabilities */}
          <div className="space-y-3">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-900 dark:text-slate-200">
              Platform
            </h4>
            <ul className="space-y-2 text-xs">
              <li>
                <a href="#product" className="hover:text-slate-900 dark:hover:text-white transition-colors">
                  Financial Overview
                </a>
              </li>
              <li>
                <a href="#features" className="hover:text-slate-900 dark:hover:text-white transition-colors">
                  Semantic Transaction Search
                </a>
              </li>
              <li>
                <a href="#features" className="hover:text-slate-900 dark:hover:text-white transition-colors">
                  Explainable Anomaly Detection
                </a>
              </li>
              <li>
                <a href="#features" className="hover:text-slate-900 dark:hover:text-white transition-colors">
                  Evidence-Backed AI Assistant
                </a>
              </li>
            </ul>
          </div>

          {/* Col 3: Architecture & Security */}
          <div className="space-y-3">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-900 dark:text-slate-200">
              Architecture
            </h4>
            <ul className="space-y-2 text-xs">
              <li>
                <a href="#how-it-works" className="hover:text-slate-900 dark:hover:text-white transition-colors">
                  IBM Db2 12.1 Ledger & Vectors
                </a>
              </li>
              <li>
                <a href="#how-it-works" className="hover:text-slate-900 dark:hover:text-white transition-colors">
                  LangChain & langchain-db2
                </a>
              </li>
              <li>
                <a href="#how-it-works" className="hover:text-slate-900 dark:hover:text-white transition-colors">
                  Rust Axum API Gateway
                </a>
              </li>
              <li>
                <a href="#how-it-works" className="hover:text-slate-900 dark:hover:text-white transition-colors">
                  Strict Multi-Tenant Isolation
                </a>
              </li>
            </ul>
          </div>

          {/* Col 4: Account Actions */}
          <div className="space-y-3">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-900 dark:text-slate-200">
              Access
            </h4>
            <div className="space-y-2 text-xs">
              <div>
                <button
                  onClick={() => onNavigate('/login')}
                  className="hover:text-slate-900 dark:hover:text-white transition-colors"
                >
                  Sign In to Workspace
                </button>
              </div>
              <div>
                <button
                  onClick={() => onNavigate('/register')}
                  className="hover:text-slate-900 dark:hover:text-white transition-colors"
                >
                  Create Demo Account
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Bottom separator */}
        <div className="mt-12 pt-8 border-t border-slate-200/80 dark:border-slate-800/80 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-500">
          <p>© 2026 FinSight AI. Built for IBM Db2Hack 2026.</p>
          <div className="mt-4 sm:mt-0 flex items-center space-x-6">
            <span>Authoritative Source of Truth: IBM Db2</span>
            <span>AI Framework: LangChain</span>
          </div>
        </div>
      </div>
    </footer>
  );
};
