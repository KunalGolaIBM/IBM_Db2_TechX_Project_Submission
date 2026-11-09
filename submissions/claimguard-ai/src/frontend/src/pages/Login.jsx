import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ShieldCheck, Lock, User, ArrowRight, AlertCircle, Database } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function Login() {
  const [username, setUsername] = useState('examiner');
  const [password, setPassword] = useState('examiner123');
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    const res = await login(username, password);
    setSubmitting(false);
    if (res.success) {
      navigate('/');
    } else {
      setError(res.error || 'Authentication failed. Please verify credentials.');
    }
  };

  const handleQuickLogin = (role) => {
    if (role === 'examiner') {
      setUsername('examiner');
      setPassword('examiner123');
    } else {
      setUsername('admin');
      setPassword('admin123');
    }
  };

  return (
    <div className="min-h-[calc(100vh-3rem)] flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-white border border-[#E0E0E0] shadow-sm rounded-sm p-8">
        <div className="flex items-center space-x-2 pb-4 border-b border-[#E0E0E0]">
          <div className="w-8 h-8 bg-[#0F62FE] flex items-center justify-center text-white rounded-sm">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-base font-bold text-[#161616]">ClaimGuard AI Portal</h1>
            <p className="text-[11px] text-[#525252]">Authorized Examiner Access • IBM Db2</p>
          </div>
        </div>

        {error && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label className="block text-xs font-semibold text-[#161616] uppercase font-mono tracking-wider">
              Username
            </label>
            <div className="mt-1 relative">
              <User className="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                className="w-full pl-9 pr-3 py-2 bg-[#F4F4F4] border border-[#E0E0E0] text-xs text-[#161616] focus:outline-none focus:border-[#0F62FE] focus:bg-white rounded-sm font-mono"
                placeholder="examiner"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-[#161616] uppercase font-mono tracking-wider">
              Password
            </label>
            <div className="mt-1 relative">
              <Lock className="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full pl-9 pr-3 py-2 bg-[#F4F4F4] border border-[#E0E0E0] text-xs text-[#161616] focus:outline-none focus:border-[#0F62FE] focus:bg-white rounded-sm font-mono"
                placeholder="••••••••"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full mt-4 flex items-center justify-center space-x-2 py-2.5 bg-[#0F62FE] hover:bg-[#0353E9] text-white text-xs font-semibold transition-colors rounded-sm shadow-sm"
          >
            <span>{submitting ? 'Authenticating...' : 'Sign In to Dashboard'}</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </form>

        {/* Quick Demo Credentials */}
        <div className="mt-6 pt-4 border-t border-gray-100">
          <p className="text-[11px] font-mono text-[#525252] uppercase text-center mb-2">
            One-Click Demo Credentials
          </p>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => handleQuickLogin('examiner')}
              className="py-1.5 px-2 bg-gray-50 hover:bg-gray-100 border border-gray-200 text-[11px] font-medium text-gray-700 rounded-sm text-center"
            >
              👤 Claims Examiner
            </button>
            <button
              type="button"
              onClick={() => handleQuickLogin('admin')}
              className="py-1.5 px-2 bg-gray-50 hover:bg-gray-100 border border-gray-200 text-[11px] font-medium text-gray-700 rounded-sm text-center"
            >
              🛡️ System Admin
            </button>
          </div>
        </div>

        <div className="mt-6 flex items-center justify-center space-x-1.5 text-[11px] text-gray-400">
          <Database className="w-3.5 h-3.5" />
          <span>IBM Db2 Relational Authentication Store</span>
        </div>
      </div>
    </div>
  );
}
