import React, { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../stores/authStore';
import { CheckCircle2, ChevronRight, MapPin, Cpu, UploadCloud, Info } from 'lucide-react';

const Onboarding = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { login } = useAuthStore();
  const role = location.state?.role || 'seller';

  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState({
    fullName: '',
    email: '',
    password: '',
    orgName: '',
    // Seller Specific
    projectType: 'agroforestry',
    area: '',
    deviceId: '',
  });

  const totalSteps = role === 'seller' ? 4 : 2;

  const handleNext = (e) => {
    e.preventDefault();
    if (step < totalSteps) {
      setStep(step + 1);
    } else {
      // Submit & Login
      login(formData.email || `new@${role}.com`, role);
      navigate(`/${role}/dashboard`);
    }
  };

  const renderProgress = () => (
    <div className="flex items-center gap-2 mb-8">
      {Array.from({ length: totalSteps }).map((_, i) => (
        <React.Fragment key={i}>
          <div className={`h-2 flex-1 rounded-full overflow-hidden ${i + 1 <= step ? 'bg-carbon-900' : 'bg-dark-800'}`}>
            <div 
              className={`h-full bg-gradient-to-r from-carbon-500 to-emerald-400 transition-all duration-500`}
              style={{ width: i + 1 < step ? '100%' : i + 1 === step ? '50%' : '0%' }}
            />
          </div>
        </React.Fragment>
      ))}
    </div>
  );

  return (
    <div className="glass-card p-8 shadow-2xl relative w-[500px] max-w-full -ml-8">
      {renderProgress()}

      <form onSubmit={handleNext}>
        {/* Step 1: Base KYC */}
        {step === 1 && (
          <div className="animate-in fade-in slide-in-from-right-4 duration-300">
            <h2 className="text-2xl font-bold text-white mb-2">Create Profile</h2>
            <p className="text-gray-400 mb-6">Let's start with your basic details.</p>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Full Name</label>
                <input required type="text" className="input-field" placeholder="John Doe" 
                  value={formData.fullName} onChange={e => setFormData({...formData, fullName: e.target.value})} />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Email</label>
                <input required type="email" className="input-field" placeholder="john@example.com" 
                  value={formData.email} onChange={e => setFormData({...formData, email: e.target.value})} />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">Password</label>
                  <input required type="password" className="input-field" placeholder="••••••••" 
                    value={formData.password} onChange={e => setFormData({...formData, password: e.target.value})} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">Organization</label>
                  <input required type="text" className="input-field" placeholder="Company Ltd" 
                    value={formData.orgName} onChange={e => setFormData({...formData, orgName: e.target.value})} />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Step 2 (General / Buyer Finish) */}
        {step === 2 && role !== 'seller' && (
          <div className="animate-in fade-in slide-in-from-right-4 duration-300">
            <h2 className="text-2xl font-bold text-white mb-2">ESG Goals</h2>
            <p className="text-gray-400 mb-6">Help us tailor your marketplace experience.</p>
            
            <div className="space-y-4">
               <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">Annual Offset Target (Tonnes CO₂)</label>
                  <input type="number" className="input-field" placeholder="e.g. 5000" />
               </div>
               <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">Industry Sector</label>
                  <select className="input-field appearance-none">
                    <option>Technology & Software</option>
                    <option>Manufacturing</option>
                    <option>Logistics & Transport</option>
                    <option>Finance</option>
                    <option>Other</option>
                  </select>
               </div>
               
               <div className="mt-6 p-4 bg-blue-500/10 border border-blue-500/20 rounded-xl flex items-start gap-3">
                 <Info className="text-blue-400 shrink-0 mt-0.5" size={18} />
                 <p className="text-sm text-blue-200 leading-relaxed">
                   As a buyer on CarbonChain, you get instant access to live sensor data for all your continuous offsets, eliminating double-counting risks.
                 </p>
               </div>
            </div>
          </div>
        )}

        {/* Step 2 (Seller) - Project */}
        {step === 2 && role === 'seller' && (
          <div className="animate-in fade-in slide-in-from-right-4 duration-300">
            <h2 className="text-2xl font-bold text-white mb-2">Project Details</h2>
            <p className="text-gray-400 mb-6">Register your carbon offset project.</p>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Project Name</label>
                <input required type="text" className="input-field" placeholder="e.g. Sahyadri Agroforestry" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">Type</label>
                  <select className="input-field appearance-none" value={formData.projectType} onChange={e => setFormData({...formData, projectType: e.target.value})}>
                    <option value="forestry">Forestry</option>
                    <option value="agroforestry">Agroforestry</option>
                    <option value="solar">Solar Energy</option>
                    <option value="biogas">Biogas</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">Area (Acres)</label>
                  <input required type="number" className="input-field" placeholder="100" 
                    value={formData.area} onChange={e => setFormData({...formData, area: e.target.value})} />
                </div>
              </div>
              
               <div className="mt-4 p-4 border border-dashed border-carbon-800 rounded-xl text-center hover:bg-carbon-900/30 transition-colors cursor-pointer group">
                  <div className="w-10 h-10 bg-dark-800 rounded-full flex items-center justify-center mx-auto mb-2 group-hover:bg-carbon-800 transition-colors">
                    <UploadCloud size={20} className="text-gray-400 group-hover:text-carbon-400" />
                  </div>
                  <p className="text-sm font-medium text-gray-300 mb-1">Upload Project Documentation</p>
                  <p className="text-xs text-gray-500">PDFs of land deeds or previous methodology audits</p>
               </div>
            </div>
          </div>
        )}

        {/* Step 3 (Seller) - Location */}
        {step === 3 && role === 'seller' && (
          <div className="animate-in fade-in slide-in-from-right-4 duration-300">
            <h2 className="text-2xl font-bold text-white mb-2">Location Mapping</h2>
            <p className="text-gray-400 mb-6">Where is this project located?</p>
            
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">State</label>
                  <input required type="text" className="input-field" placeholder="Maharashtra" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">District</label>
                  <input required type="text" className="input-field" placeholder="Pune" />
                </div>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2 flex items-center gap-2">
                  <MapPin size={16} className="text-carbon-500" /> Plot Coordinates
                </label>
                <div className="h-40 rounded-xl border border-carbon-800 bg-[url('https://maps.googleapis.com/maps/api/staticmap?center=20.5937,78.9629&zoom=5&size=500x200&maptype=satellite&key=YOUR_API_KEY')] bg-cover bg-center flex items-center justify-center relative overflow-hidden group cursor-pointer">
                  <div className="absolute inset-0 bg-dark-900/60 group-hover:bg-dark-900/40 transition-colors" />
                  <div className="btn-secondary relative z-10 pointer-events-none text-sm px-4 py-2">
                    Open Map Picker to draw boundaries
                  </div>
                </div>
                <p className="text-xs text-gray-500 mt-2">These boundaries will be used to cross-reference satellite data.</p>
              </div>
            </div>
          </div>
        )}

        {/* Step 4 (Seller) - IoT Pair */}
        {step === 4 && role === 'seller' && (
          <div className="animate-in fade-in slide-in-from-right-4 duration-300">
            <h2 className="text-2xl font-bold text-white mb-2">Pair IoT Sensor</h2>
            <p className="text-gray-400 mb-6">Connect your field device to start the dMRV pipeline.</p>
            
            <div className="space-y-6">
              <div className="p-4 bg-dark-800 rounded-xl border border-carbon-800 flex gap-4">
                <div className="w-12 h-12 rounded-lg bg-carbon-900/50 border border-carbon-700 flex items-center justify-center shrink-0">
                  <Cpu className="text-carbon-400" />
                </div>
                <div>
                  <h4 className="font-semibold text-gray-200 text-sm mb-1">CarbonChain Node v2</h4>
                  <p className="text-xs text-gray-500 leading-relaxed">Turn on your device and wait for the blue light to blink before entering the ID.</p>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Device ID / Token</label>
                <input 
                  required 
                  type="text" 
                  className="input-field font-mono text-center tracking-widest uppercase text-lg" 
                  placeholder="DEV-XXXX" 
                  value={formData.deviceId}
                  onChange={e => setFormData({...formData, deviceId: e.target.value.toUpperCase()})}
                />
              </div>

              {formData.deviceId.length > 5 && (
                <div className="animate-in fade-in zoom-in text-center p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-sm flex items-center justify-center gap-2">
                  <CheckCircle2 size={16} /> Connection Established
                </div>
              )}
            </div>
          </div>
        )}

        <div className="mt-10 flex gap-4">
          {step > 1 && (
            <button 
              type="button" 
              onClick={() => setStep(step - 1)}
              className="px-6 py-3 rounded-xl font-medium text-gray-400 hover:text-white bg-dark-800 hover:bg-dark-700 transition-colors w-1/3"
            >
              Back
            </button>
          )}
          <button 
            type="submit" 
            className="btn-primary flexitems-center justify-center flex-1 py-3"
          >
            {step === totalSteps ? 'Complete Setup' : 'Continue'}
          </button>
        </div>
      </form>
    </div>
  );
};

export default Onboarding;
