import React from 'react';
import { Link } from 'react-router-dom';
import { Leaf, Globe2, ShieldCheck, Activity, ArrowRight, CheckCircle2 } from 'lucide-react';
import { useMarketDataStore } from '../stores/marketStore';

const LandingPage = () => {
  const { platformStats } = useMarketDataStore();

  return (
    <div className="min-h-screen">
      {/* Hero Section */}
      <section className="relative pt-32 pb-20 lg:pt-48 lg:pb-32 overflow-hidden">
        {/* Animated Background */}
        <div className="absolute inset-0 z-0">
          <div className="absolute top-1/4 left-1/4 w-[500px] h-[500px] bg-carbon-500/10 rounded-full blur-[120px] mix-blend-screen animate-pulse-slow" />
          <div className="absolute bottom-1/4 right-1/4 w-[600px] h-[600px] bg-emerald-600/10 rounded-full blur-[150px] mix-blend-screen animate-float" />
          <div className="absolute inset-0 bg-[url('https://www.transparenttextures.com/patterns/cubes.png')] opacity-5 mix-blend-overlay"></div>
        </div>

        <div className="container mx-auto px-6 relative z-10">
          <div className="max-w-4xl mx-auto text-center">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-carbon-900/50 border border-carbon-500/30 text-carbon-300 text-sm font-medium mb-8 backdrop-blur-md">
              <span className="live-dot" />
              Live dMRV Marketplace
            </div>
            
            <h1 className="text-5xl lg:text-7xl font-extrabold tracking-tight text-white mb-6">
              Trade carbon credits with <br />
              <span className="text-gradient">absolute integrity.</span>
            </h1>
            
            <p className="text-xl text-gray-400 mb-10 max-w-2xl mx-auto leading-relaxed">
              CarbonChain uses real-time IoT sensors and AI to verify carbon sequestration continuously. Say goodbye to greenwashing and delayed manual audits.
            </p>

            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link to="/marketplace" className="btn-primary flex items-center gap-2 text-lg px-8 py-4 w-full sm:w-auto justify-center">
                Browse Marketplace <ArrowRight size={20} />
              </Link>
              <Link to="/auth/signup" className="btn-secondary text-lg px-8 py-4 w-full sm:w-auto justify-center">
                List a Project
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Live Stats Bar */}
      <section className="border-y border-carbon-800/40 bg-dark-800/50 backdrop-blur-md py-8">
        <div className="container mx-auto px-6">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-8 divide-x divide-carbon-800/40 text-center">
            <div>
              <p className="text-3xl font-bold text-white mb-1">{platformStats.totalCreditsListed.toLocaleString()}</p>
              <p className="text-sm text-gray-500 uppercase tracking-wider">Tonnes Listed</p>
            </div>
            <div>
              <p className="text-3xl font-bold text-carbon-400 mb-1">{(platformStats.totalGMV / 100000).toFixed(1)}L</p>
              <p className="text-sm text-gray-500 uppercase tracking-wider">GMV (INR)</p>
            </div>
            <div>
              <p className="text-3xl font-bold text-white mb-1">{platformStats.activeSensors}</p>
              <p className="text-sm text-gray-500 uppercase tracking-wider">Active Sensors</p>
            </div>
            <div>
              <p className="text-3xl font-bold text-amber-400 mb-1">{platformStats.avgQualityScore.toFixed(1)}/100</p>
              <p className="text-sm text-gray-500 uppercase tracking-wider">Avg Quality Score</p>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="tech" className="py-24 bg-dark-900">
        <div className="container mx-auto px-6">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <h2 className="section-title text-4xl mb-4">How CarbonChain Works</h2>
            <p className="text-gray-400">Our seamless dMRV pipeline automates trust from the soil to the certificate.</p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {/* Feature 1 */}
            <div className="glass-card p-8 group hover:-translate-y-2 transition-transform duration-300">
              <div className="w-14 h-14 rounded-2xl bg-carbon-900/50 border border-carbon-700/50 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                <Activity className="w-7 h-7 text-carbon-400" />
              </div>
              <h3 className="text-xl font-bold text-white mb-3">Live IoT Data</h3>
              <p className="text-gray-400 leading-relaxed">
                Sensors deployed in the field stream CO₂, temperature, PM2.5, and soil moisture data directly to our platform every 5 seconds.
              </p>
            </div>

            {/* Feature 2 */}
            <div className="glass-card p-8 group hover:-translate-y-2 transition-transform duration-300 delay-100">
              <div className="w-14 h-14 rounded-2xl bg-amber-900/20 border border-amber-700/30 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                <ShieldCheck className="w-7 h-7 text-amber-400" />
              </div>
              <h3 className="text-xl font-bold text-white mb-3">AI Quality Scoring</h3>
              <p className="text-gray-400 leading-relaxed">
                Raw sensor data feeds into our ML models to generate a real-time Quality Score (0-100), adjusting listing prices dynamically.
              </p>
            </div>

            {/* Feature 3 */}
            <div className="glass-card p-8 group hover:-translate-y-2 transition-transform duration-300 delay-200">
              <div className="w-14 h-14 rounded-2xl bg-blue-900/20 border border-blue-700/30 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                <Globe2 className="w-7 h-7 text-blue-400" />
              </div>
              <h3 className="text-xl font-bold text-white mb-3">Transparent Trading</h3>
              <p className="text-gray-400 leading-relaxed">
                Buyers purchase credits backed by verifiable telemetry and satellite data, eliminating greenwashing and middleman markups.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-dark-900 to-carbon-950 z-0"/>
        <div className="container mx-auto px-6 relative z-10">
          <div className="glass-card border-carbon-600/30 overflow-hidden">
            <div className="absolute block w-full h-full bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-carbon-500/20 via-transparent to-transparent opacity-60 pointer-events-none"></div>
            
            <div className="grid lg:grid-cols-2 gap-12 items-center p-12 lg:p-20">
              <div>
                <h2 className="text-4xl font-bold text-white mb-6">Democratizing Carbon Markets for Smallholders.</h2>
                <ul className="space-y-4 mb-8">
                  {[
                    "No upfront verification costs",
                    "Direct payout to your bank account",
                    "Instant global buyer access",
                    "Continuous automated dMRV"
                  ].map((item, i) => (
                    <li key={i} className="flex items-center gap-3 text-gray-300">
                      <CheckCircle2 className="w-5 h-5 text-carbon-400 shrink-0" />
                      {item}
                    </li>
                  ))}
                </ul>
                <Link to="/auth/signup" className="btn-primary inline-flex">
                  Register Your Project
                </Link>
              </div>
              
              <div className="relative">
                <div className="absolute inset-0 bg-gradient-to-tr from-carbon-500/20 to-emerald-500/20 blur-3xl rounded-full" />
                <img 
                  src="https://images.unsplash.com/photo-1542601906990-b4d3fb778b09?auto=format&fit=crop&q=80&w=800" 
                  alt="Farmer" 
                  className="rounded-2xl border border-carbon-700/50 shadow-2xl relative z-10 w-full object-cover h-[400px]"
                />
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
};

export default LandingPage;
