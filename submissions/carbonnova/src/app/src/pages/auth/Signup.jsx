import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Sprout, Building2, ShieldCheck, ClipboardCheck, ArrowRight } from 'lucide-react';

const Signup = () => {
  const navigate = useNavigate();
  const [selectedRole, setSelectedRole] = useState(null);

  const roles = [
    {
      id: 'seller',
      title: 'Project Developer / Farmer',
      desc: 'Connect IoT sensors and mint AI-verified carbon credits.',
      icon: Sprout,
      color: 'text-emerald-400',
      bg: 'bg-emerald-400/10',
      border: 'border-emerald-500/30'
    },
    {
      id: 'buyer',
      title: 'Corporate Buyer',
      desc: 'Purchase high-integrity credits to meet ESG and compliance targets.',
      icon: Building2,
      color: 'text-blue-400',
      bg: 'bg-blue-400/10',
      border: 'border-blue-500/30'
    },
    {
      id: 'verifier',
      title: 'Third-Party Auditor',
      desc: 'Review satellite data and physical audits for listed projects.',
      icon: ClipboardCheck,
      color: 'text-amber-400',
      bg: 'bg-amber-400/10',
      border: 'border-amber-500/30'
    }
  ];

  const handleContinue = () => {
    if (selectedRole) {
      navigate('/auth/onboarding', { state: { role: selectedRole } });
    }
  };

  return (
    <div className="glass-card p-8 shadow-2xl">
      <h2 className="text-3xl font-bold text-white mb-2">Create an Account</h2>
      <p className="text-gray-400 mb-8">How do you want to use CarbonChain?</p>

      <div className="space-y-4 mb-8">
        {roles.map((role) => {
          const Icon = role.icon;
          const isSelected = selectedRole === role.id;
          
          return (
            <button
              key={role.id}
              onClick={() => setSelectedRole(role.id)}
              className={`w-full text-left p-5 rounded-2xl border transition-all duration-200 flex items-start gap-4 ${
                isSelected 
                  ? `${role.border} bg-dark-700/80 shadow-[inset_0_0_20px_rgba(0,0,0,0.2)]` 
                  : 'border-carbon-800/40 bg-dark-800/40 hover:bg-dark-700 hover:border-carbon-700'
              }`}
            >
              <div className={`p-3 rounded-xl shrink-0 ${isSelected ? role.bg : 'bg-dark-900 border border-carbon-800'}`}>
                <Icon className={`w-6 h-6 ${isSelected ? role.color : 'text-gray-500'}`} />
              </div>
              <div>
                <h3 className={`font-bold mb-1 ${isSelected ? 'text-white' : 'text-gray-300'}`}>
                  {role.title}
                </h3>
                <p className={`text-sm leading-relaxed ${isSelected ? 'text-gray-300' : 'text-gray-500'}`}>
                  {role.desc}
                </p>
              </div>
              
              <div className={`ml-auto w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0 mt-3 ${
                isSelected ? 'border-carbon-500' : 'border-gray-600'
              }`}>
                {isSelected && <div className="w-2.5 h-2.5 rounded-full bg-carbon-500" />}
              </div>
            </button>
          );
        })}
      </div>

      <button 
        onClick={handleContinue}
        disabled={!selectedRole}
        className="w-full btn-primary flex items-center justify-center gap-2 py-3"
      >
        Continue <ArrowRight size={20} />
      </button>

      <div className="mt-6 text-center">
        <p className="text-sm text-gray-400">
          Already have an account?{' '}
          <Link to="/auth/login" className="text-carbon-400 font-semibold hover:text-carbon-300">
            Log in
          </Link>
        </p>
      </div>
    </div>
  );
};

export default Signup;
