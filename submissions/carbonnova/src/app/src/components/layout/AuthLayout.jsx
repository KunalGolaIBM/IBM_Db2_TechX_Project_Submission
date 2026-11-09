import React from 'react';
import { Outlet, Link } from 'react-router-dom';
import { Leaf } from 'lucide-react';

const AuthLayout = () => {
  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden">
      {/* Background embellishments */}
      <div className="absolute top-[-10%] right-[-5%] w-[50vw] h-[50vw] bg-carbon-900/40 rounded-full blur-[120px] mix-blend-screen pointer-events-none" />
      <div className="absolute bottom-[-10%] left-[-10%] w-[60vw] h-[60vw] bg-emerald-900/30 rounded-full blur-[150px] mix-blend-screen pointer-events-none" />

      <div className="w-full max-w-md mx-4 z-10">
        <div className="text-center mb-10">
          <Link to="/" className="inline-flex items-center gap-2 mb-4">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-carbon-500 to-emerald-400 flex items-center justify-center shadow-lg shadow-carbon-500/30">
              <Leaf className="w-6 h-6 text-dark-900" />
            </div>
            <span className="text-2xl font-bold tracking-tight">CarbonChain</span>
          </Link>
          <p className="text-gray-400">The transparent dMRV carbon marketplace.</p>
        </div>
        
        <Outlet />
      </div>
    </div>
  );
};

export default AuthLayout;
