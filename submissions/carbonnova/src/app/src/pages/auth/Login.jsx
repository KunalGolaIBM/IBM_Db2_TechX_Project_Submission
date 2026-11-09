import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../stores/authStore';
import { Mail, Lock, LogIn } from 'lucide-react';

const Login = () => {
  const navigate = useNavigate();
  const { login } = useAuthStore();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('seller'); // Default mock role for login

  const handleSubmit = (e) => {
    e.preventDefault();
    if (email && password) {
      // Mock login - just accept any valid looking email for demo
      login(email, role);
      navigate(`/${role}/dashboard`);
    }
  };

  return (
    <div className="glass-card p-8 shadow-2xl">
      <h2 className="text-3xl font-bold text-white mb-2">Welcome Back</h2>
      <p className="text-gray-400 mb-8">Log in to manage your carbon credits.</p>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">Account Type (Demo Profile)</label>
          <div className="grid grid-cols-4 gap-2 mb-4">
            {['seller', 'buyer', 'admin', 'verifier'].map((r) => (
              <button
                key={r}
                type="button"
                onClick={() => setRole(r)}
                className={`py-2 text-xs font-semibold rounded-lg capitalize border ${
                  role === r 
                    ? 'bg-carbon-900 border-carbon-500 text-carbon-400' 
                    : 'bg-dark-800 border-carbon-800/40 text-gray-400 hover:text-gray-200'
                }`}
              >
                {r}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">Email Address</label>
          <div className="relative">
            <Mail className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500 w-5 h-5" />
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="input-field pl-12"
              placeholder={`demo@${role}.com`}
            />
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="block text-sm font-medium text-gray-300">Password</label>
            <a href="#" className="text-xs text-carbon-400 hover:text-carbon-300">Forgot password?</a>
          </div>
          <div className="relative">
            <Lock className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500 w-5 h-5" />
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input-field pl-12"
              placeholder="••••••••"
            />
          </div>
        </div>

        <button type="submit" className="w-full btn-primary flex items-center justify-center gap-2 py-3">
          <LogIn size={20} />
          Sign In
        </button>
      </form>

      <div className="mt-8 text-center">
        <p className="text-sm text-gray-400">
          Don't have an account?{' '}
          <Link to="/auth/signup" className="text-carbon-400 font-semibold hover:text-carbon-300">
            Sign up
          </Link>
        </p>
      </div>

      <div className="mt-6 pt-6 border-t border-carbon-800/40 text-center">
         <p className="text-xs text-gray-500 mb-3">Demo Credentials</p>
         <div className="flex justify-center gap-4 text-xs font-mono">
            <button onClick={() => {setEmail('raj@greenfarm.in'); setPassword('password'); setRole('seller')}} className="text-carbon-500 hover:underline">Seller</button>
            <button onClick={() => {setEmail('amit@tatasteel.com'); setPassword('password'); setRole('buyer')}} className="text-carbon-500 hover:underline">Buyer</button>
            <button onClick={() => {setEmail('admin@carbonchain.in'); setPassword('password'); setRole('admin')}} className="text-carbon-500 hover:underline">Admin</button>
         </div>
      </div>
    </div>
  );
};

export default Login;
