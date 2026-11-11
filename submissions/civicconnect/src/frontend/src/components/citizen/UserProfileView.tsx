import React, { useState } from 'react';
import {
  User,
  Mail,
  Shield,
  Building,
  Calendar,
  Save,
  CheckCircle2,
  Database,
  LogIn
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export const UserProfileView: React.FC = () => {
  const { userProfile, currentUser, updateProfileData, loginWithGoogle } = useAuth();
  const [name, setName] = useState(userProfile?.name || '');
  const [saved, setSaved] = useState(false);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    await updateProfileData({ name: name.trim() });
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-900">User Profile & Account</h1>
        <p className="text-xs text-slate-500">Manage your municipal citizen credentials and contact identity</p>
      </div>

      <div className="p-6 rounded-2xl bg-white border border-slate-200/90 shadow-xs space-y-6">
        <div className="flex items-center gap-4 pb-6 border-b border-slate-100">
          <div className="w-14 h-14 rounded-2xl bg-teal-600 text-white flex items-center justify-center font-bold text-xl shadow-md">
            {userProfile?.name?.charAt(0) || 'U'}
          </div>
          <div>
            <h2 className="text-base font-bold text-slate-900">{userProfile?.name}</h2>
            <p className="text-xs text-slate-500">{userProfile?.email}</p>
            <div className="mt-1 flex items-center gap-2">
              <span className="text-[11px] font-semibold bg-teal-50 text-teal-800 px-2.5 py-0.5 rounded-full border border-teal-200 uppercase">
                Role: {userProfile?.role}
              </span>
              <span className="text-[11px] text-emerald-600 font-medium flex items-center gap-1">
                <Database className="w-3 h-3" />
                Firebase Cloud Connected
              </span>
            </div>
          </div>
        </div>

        {saved && (
          <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-800 text-xs flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            <span>Profile successfully updated in Firestore database.</span>
          </div>
        )}

        <form onSubmit={handleSave} className="space-y-4">
          <div>
            <label className="block text-xs font-bold uppercase text-slate-700 mb-1">Full Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3.5 py-2 text-xs sm:text-sm rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-teal-500"
            />
          </div>

          <div>
            <label className="block text-xs font-bold uppercase text-slate-700 mb-1">Email Address</label>
            <input
              type="email"
              value={userProfile?.email || ''}
              disabled
              className="w-full px-3.5 py-2 text-xs sm:text-sm rounded-xl border border-slate-200 bg-slate-50 text-slate-500 cursor-not-allowed"
            />
          </div>

          <div>
            <label className="block text-xs font-bold uppercase text-slate-700 mb-1">User Identifier (UID)</label>
            <input
              type="text"
              value={userProfile?.uid || ''}
              disabled
              className="w-full font-mono text-[11px] px-3.5 py-2 rounded-xl border border-slate-200 bg-slate-50 text-slate-500 cursor-not-allowed"
            />
          </div>

          <div className="pt-3 border-t border-slate-100 flex items-center justify-between">
            {!currentUser && (
              <button
                type="button"
                onClick={loginWithGoogle}
                className="text-xs text-teal-700 hover:text-teal-800 font-semibold flex items-center gap-1"
              >
                <LogIn className="w-3.5 h-3.5" />
                <span>Link Official Google Account</span>
              </button>
            )}
            <button
              type="submit"
              className="ml-auto px-5 py-2 rounded-xl bg-teal-600 hover:bg-teal-500 text-white text-xs font-semibold shadow-xs transition flex items-center gap-1.5"
            >
              <Save className="w-4 h-4" />
              <span>Save Changes</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
