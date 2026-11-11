import Link from 'next/link';

export default function LandingPage() {
  return (
    <div className="min-h-screen flex flex-col bg-white text-slate-900">
      {/* Navigation */}
      <header className="border-b border-slate-200 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-lg bg-primary-600 flex items-center justify-center text-white">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <span className="text-xl font-bold tracking-tight text-slate-900">SplitSync AI</span>
          </div>
          <div className="flex items-center space-x-4">
            <Link
              href="/login"
              className="px-4 py-2 text-sm font-medium text-slate-700 hover:text-slate-900 transition-colors"
            >
              Sign In
            </Link>
            <Link
              href="/register"
              className="px-4 py-2 text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 rounded-md transition-colors"
            >
              Get Started
            </Link>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="py-20 sm:py-28 bg-slate-50 border-b border-slate-200">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <div className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-primary-100 text-primary-800 mb-6">
            Enterprise Group Expense Settlement & Reconciliation
          </div>
          <h1 className="text-4xl sm:text-5xl font-extrabold text-slate-900 tracking-tight leading-tight">
            SplitSync AI
          </h1>
          <p className="mt-4 text-xl sm:text-2xl font-normal text-slate-700 leading-relaxed">
            AI-assisted group payment tracking, verified cash approvals, and fair expense reconciliation.
          </p>
          <p className="mt-4 max-w-2xl mx-auto text-base text-slate-600">
            Engineered for precision down to the last paisa. Reconcile complex group trips, events, and shared accounts with automated settlement minimization and dual-custody cash verification.
          </p>
          <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              href="/register"
              className="w-full sm:w-auto px-8 py-3 text-base font-semibold text-white bg-primary-600 hover:bg-primary-700 rounded-md shadow-sm transition-colors text-center"
            >
              Get Started
            </Link>
            <Link
              href="/login"
              className="w-full sm:w-auto px-8 py-3 text-base font-semibold text-slate-700 bg-white hover:bg-slate-100 border border-slate-300 rounded-md shadow-sm transition-colors text-center"
            >
              Sign In
            </Link>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-20 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto mb-16">
            <h2 className="text-3xl font-bold tracking-tight text-slate-900">
              Complete Financial Integrity for Shared Expenses
            </h2>
            <p className="mt-3 text-lg text-slate-600">
              Designed for transparency, auditability, and speed across every contribution and payout.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {/* Feature 1 */}
            <div className="p-6 rounded-lg border border-slate-200 bg-white hover:border-slate-300 transition-colors">
              <div className="w-10 h-10 rounded-md bg-primary-50 text-primary-600 flex items-center justify-center mb-4">
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h4M4 12h4m12 0h.01M5 8h2a1 1 0 001-1V5a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1zm12 0h2a1 1 0 001-1V5a1 1 0 00-1-1h-2a1 1 0 00-1 1v2a1 1 0 001 1zM5 20h2a1 1 0 001-1v-2a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1z" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-slate-900 mb-2">Smart Payment Tracking</h3>
              <p className="text-slate-600 text-sm leading-relaxed">
                Seamless QR-based group contributions with real-time transaction verification and idempotency keys to eliminate double debits.
              </p>
            </div>

            {/* Feature 2 */}
            <div className="p-6 rounded-lg border border-slate-200 bg-white hover:border-slate-300 transition-colors">
              <div className="w-10 h-10 rounded-md bg-emerald-50 text-emerald-600 flex items-center justify-center mb-4">
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-slate-900 mb-2">Cash Management</h3>
              <p className="text-slate-600 text-sm leading-relaxed">
                Verified physical cash contributions with an immutable dual-custody approval workflow to ensure all cash claims are peer-reviewed.
              </p>
            </div>

            {/* Feature 3 */}
            <div className="p-6 rounded-lg border border-slate-200 bg-white hover:border-slate-300 transition-colors">
              <div className="w-10 h-10 rounded-md bg-indigo-50 text-indigo-600 flex items-center justify-center mb-4">
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-slate-900 mb-2">Expense Splitting</h3>
              <p className="text-slate-600 text-sm leading-relaxed">
                Fair, accurate splitting to the last paisa with integer arithmetic, eliminating rounding drift across group participants.
              </p>
            </div>

            {/* Feature 4 */}
            <div className="p-6 rounded-lg border border-slate-200 bg-white hover:border-slate-300 transition-colors">
              <div className="w-10 h-10 rounded-md bg-amber-50 text-amber-600 flex items-center justify-center mb-4">
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-slate-900 mb-2">Settlement Engine</h3>
              <p className="text-slate-600 text-sm leading-relaxed">
                Minimum-transfer graph optimization collapses complex web debts into the minimal number of direct peer-to-peer repayments.
              </p>
            </div>

            {/* Feature 5 */}
            <div className="p-6 rounded-lg border border-slate-200 bg-white hover:border-slate-300 transition-colors">
              <div className="w-10 h-10 rounded-md bg-purple-50 text-purple-600 flex items-center justify-center mb-4">
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-slate-900 mb-2">AI Assistant</h3>
              <p className="text-slate-600 text-sm leading-relaxed">
                Natural language query interface to ask questions about balances, spending patterns, anomalies, and pending settlement obligations.
              </p>
            </div>

            {/* Feature 6 */}
            <div className="p-6 rounded-lg border border-slate-200 bg-white hover:border-slate-300 transition-colors">
              <div className="w-10 h-10 rounded-md bg-blue-50 text-blue-600 flex items-center justify-center mb-4">
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-slate-900 mb-2">IBM Db2 Powered</h3>
              <p className="text-slate-600 text-sm leading-relaxed">
                Enterprise-grade ACID transactions, strict constraints, and immutable audit logs backed by IBM Db2 relational database technology.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="mt-auto border-t border-slate-200 bg-slate-50 py-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between text-sm text-slate-500">
          <p>&copy; {new Date().getFullYear()} SplitSync AI. Built for the IBM Db2 TechX Summit 2026.</p>
          <div className="mt-4 sm:mt-0 flex space-x-6">
            <Link href="/login" className="hover:text-slate-800 transition-colors">Login</Link>
            <Link href="/register" className="hover:text-slate-800 transition-colors">Register</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
