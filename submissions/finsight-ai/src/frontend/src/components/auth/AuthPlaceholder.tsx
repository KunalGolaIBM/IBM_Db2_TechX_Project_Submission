import React from 'react';
import { ArrowLeft, Lock, ShieldCheck, Key } from 'lucide-react';

interface AuthPlaceholderProps {
  mode: 'login' | 'register';
  onNavigate: (route: string) => void;
}

export const AuthPlaceholder: React.FC<AuthPlaceholderProps> = ({ mode, onNavigate }) => {
  const isLogin = mode === 'login';

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8 bg-slate-50/50 dark:bg-slate-950/40">
      <div className="max-w-md w-full space-y-6 p-8 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm">
        {/* Back Link */}
        <button
          onClick={() => onNavigate('/')}
          className="inline-flex items-center space-x-1.5 text-xs font-medium text-slate-500 hover:text-slate-900 dark:hover:text-white transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to FinSight AI</span>
        </button>

        {/* Header */}
        <div className="space-y-2 text-center pt-2">
          <div className="w-12 h-12 mx-auto rounded-xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-900 dark:text-white">
            <Lock className="w-6 h-6" />
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-950 dark:text-white">
            {isLogin ? 'Sign In to FinSight AI' : 'Create FinSight AI Account'}
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {isLogin
              ? 'Access your database-grounded financial intelligence workspace'
              : 'Register an isolated tenant ledger backed by IBM Db2'}
          </p>
        </div>

        {/* Milestone Notice */}
        <div className="p-4 rounded-xl border border-sky-200/80 dark:border-sky-900/60 bg-sky-50/50 dark:bg-sky-950/30 space-y-2 text-xs">
          <div className="flex items-center space-x-2 text-sky-900 dark:text-sky-300 font-semibold">
            <ShieldCheck className="w-4 h-4 text-sky-600 dark:text-sky-400" />
            <span>Frontend Authentication Target</span>
          </div>
          <p className="text-sky-800/80 dark:text-sky-300/80 leading-relaxed">
            The Rust API Gateway authentication backend (Argon2id, HttpOnly sessions, CSRF protection) is verified and healthy on port 8080. Full UI form binding will be established in the upcoming authentication milestone (Stage 3B).
          </p>
        </div>

        {/* Demo Credentials Box */}
        <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50 space-y-2.5 text-xs">
          <div className="flex items-center justify-between text-slate-700 dark:text-slate-300 font-medium">
            <span className="flex items-center space-x-1.5">
              <Key className="w-3.5 h-3.5 text-slate-500" />
              <span>Configured Seed Demo Account:</span>
            </span>
            <span className="font-mono text-[11px] text-emerald-600 dark:text-emerald-400">Active</span>
          </div>
          <div className="space-y-1 font-mono text-[11px] text-slate-600 dark:text-slate-400 bg-white dark:bg-slate-900 p-2.5 rounded-lg border border-slate-200/60 dark:border-slate-700/60">
            <div>Email: <span className="text-slate-900 dark:text-slate-200 font-semibold">alex.chen.demo@finsight.internal</span></div>
            <div>Password: <span className="text-slate-900 dark:text-slate-200 font-semibold">DemoPassword123!</span></div>
            <div>Dataset: <span className="text-slate-900 dark:text-slate-200">208 Verified Db2 Transactions</span></div>
          </div>
        </div>

        {/* Navigation Action */}
        <div className="pt-2 flex flex-col space-y-3">
          <button
            onClick={() => onNavigate('/')}
            className="w-full py-2.5 px-4 rounded-lg bg-slate-900 text-white dark:bg-white dark:text-slate-950 font-medium text-xs hover:bg-slate-800 dark:hover:bg-slate-100 transition-colors"
          >
            Return to Landing Page
          </button>
          <div className="text-center text-xs text-slate-500">
            {isLogin ? (
              <span>
                Need an account?{' '}
                <button
                  onClick={() => onNavigate('/register')}
                  className="font-medium text-slate-900 dark:text-white hover:underline"
                >
                  Register
                </button>
              </span>
            ) : (
              <span>
                Already have an account?{' '}
                <button
                  onClick={() => onNavigate('/login')}
                  className="font-medium text-slate-900 dark:text-white hover:underline"
                >
                  Sign in
                </button>
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
