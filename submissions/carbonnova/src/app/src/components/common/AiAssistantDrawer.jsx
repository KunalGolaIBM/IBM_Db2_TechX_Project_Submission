import React, { useState, useEffect } from 'react';
import { 
  Sparkles, 
  X, 
  Send, 
  Bot, 
  User, 
  AlertCircle, 
  RefreshCw, 
  HelpCircle,
  ShieldCheck,
  CheckCircle2,
  ExternalLink
} from 'lucide-react';
import api from '../../lib/api';

export const AiAssistantDrawer = ({ isOpen, onClose, activeProject, activeParcel }) => {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: `I am CarbonNova's evidence assistant. I can explain saved field observations and deterministic assessment outputs, identify missing evidence, and draft summaries. Satellite-derived indicators are unavailable unless explicitly listed as connected data. What would you like to understand?`,
      time: 'Just now',
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [aiStatus, setAiStatus] = useState(null);
  const [selectedProvider] = useState('nebius'); // Hackathon inference routes through Nebius Token Factory

  useEffect(() => {
    // Check AI server status safely
    api.aiStatus()
      .then((data) => setAiStatus(data))
      .catch(() => setAiStatus({ configured: false, error: 'Backend unreachable' }));
  }, []);

  const presets = [
    { label: 'Explain saved estimates', prompt: 'Explain the deterministic estimate and distinguish observed field data, assumptions, and modeled outputs. Identify missing inputs.' },
    { label: 'What evidence is missing?', prompt: 'List evidence missing from this project record. Do not infer laboratory, satellite, validation, or registry records.' },
    { label: 'Explain sensor readings', prompt: 'Summarize the available timestamped field readings and their source labels. Explain what they do not establish about carbon stock change.' },
    { label: 'Draft review summary', prompt: 'Draft a review-ready summary grounded only in this project’s saved data, sources, limitations, and outstanding actions.' },
  ];

  const handleSend = async (textToSend) => {
    const question = (textToSend || input).trim();
    if (!question || loading) return;

    const userMsg = {
      role: 'user',
      content: question,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    const projectId = activeProject?.id;
    if (!projectId) {
      setMessages((prev) => [...prev, { role: 'assistant', isError: true, content: 'Select a saved project before asking for evidence-backed analysis. No default demo project is silently substituted.', time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }]);
      setLoading(false);
      return;
    }

    try {
      let res;
      if (selectedProvider === 'nvidia') {
        res = await api.nvidiaAsk(projectId, question, messages);
      } else {
        res = await api.aiAsk(projectId, question, messages);
      }

      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: res.answer || res.content,
          model: res.model || 'NVIDIA Nemotron',
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          isError: true,
          content: err?.message || 'Unable to communicate with the NVIDIA Nemotron backend. Please check server/.env configuration.',
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/40 backdrop-blur-xs transition-opacity" 
        onClick={onClose} 
      />

      {/* Drawer Container */}
      <div className="relative w-full max-w-lg bg-white h-full shadow-2xl flex flex-col z-10 border-l border-[#D5E0D7] animate-in slide-in-from-right duration-200">
        
        {/* Header */}
        <div className="px-6 py-4 bg-[#0C3327] text-white flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-emerald-500/20 border border-emerald-400/40 flex items-center justify-center text-emerald-300">
              <Sparkles size={20} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-base tracking-tight">AI Carbon Intelligence</h3>
                <span className="text-[10px] uppercase font-semibold px-2 py-0.5 rounded-full bg-emerald-400/20 text-emerald-300 border border-emerald-400/30">Nebius · Nemotron</span>
              </div>
              <p className="text-xs text-emerald-100/70">Grounding with {activeParcel?.name || activeProject?.name || 'selected saved project'}</p>
            </div>
          </div>
          <button 
            onClick={onClose} 
            className="p-1.5 rounded-lg text-emerald-200 hover:text-white hover:bg-white/10 transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Status / Notice bar */}
        <div className="bg-[#F2F7F4] px-5 py-2.5 border-b border-[#E1ECE3] flex items-center justify-between text-xs text-[#2A5741]">
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${aiStatus?.configured ? 'bg-emerald-500' : 'bg-amber-500'}`} />
            <span>{aiStatus?.configured ? `${aiStatus.model} · Nebius Token Factory` : 'Nebius Token Factory not configured'}</span>
          </div>
          <span className="text-[11px] text-gray-500">{aiStatus?.model_available === true ? 'Model listed' : 'Availability unverified'}</span>
        </div>

        {/* Preset Prompt Pills */}
        <div className="p-3 bg-[#FAFBF9] border-b border-[#E4EAE4] overflow-x-auto flex gap-2 styled-scrollbar">
          {presets.map((p, i) => (
            <button
              key={i}
              onClick={() => handleSend(p.prompt)}
              className="shrink-0 text-xs px-3 py-1.5 rounded-lg bg-white border border-[#D5E0D7] text-[#1E4332] hover:bg-[#F2F7F4] hover:border-[#10B981] transition-all font-medium text-left"
            >
              {p.label}
            </button>
          ))}
        </div>

        {/* Message Thread */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4 bg-[#F8FAF8]">
          {messages.map((m, idx) => (
            <div
              key={idx}
              className={`flex gap-3 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              {m.role === 'assistant' && (
                <div className="w-8 h-8 rounded-full bg-[#0C3327] text-emerald-300 flex items-center justify-center shrink-0 mt-0.5">
                  <Bot size={16} />
                </div>
              )}

              <div
                className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                  m.role === 'user'
                    ? 'bg-[#0C3327] text-white rounded-tr-xs'
                    : m.isError
                    ? 'bg-red-50 text-red-800 border border-red-200 rounded-tl-xs'
                    : 'bg-white text-[#152B20] border border-[#E3E9E3] shadow-xs rounded-tl-xs'
                }`}
              >
                <div className="whitespace-pre-wrap">{m.content}</div>
                <div className={`mt-1.5 text-[10px] flex items-center justify-between ${
                  m.role === 'user' ? 'text-emerald-200/70' : 'text-gray-400'
                }`}>
                  <span>{m.model || (m.role === 'user' ? 'You' : 'CarbonNova AI')}</span>
                  <span>{m.time}</span>
                </div>
              </div>

              {m.role === 'user' && (
                <div className="w-8 h-8 rounded-full bg-[#1A4F3B] text-white flex items-center justify-center shrink-0 mt-0.5">
                  <User size={16} />
                </div>
              )}
            </div>
          ))}

          {loading && (
            <div className="flex gap-3 items-center text-sm text-[#3E6552]">
              <div className="w-8 h-8 rounded-full bg-[#0C3327] text-emerald-300 flex items-center justify-center shrink-0">
                <Bot size={16} />
              </div>
              <div className="bg-white border border-[#E3E9E3] rounded-2xl px-4 py-3 flex items-center gap-2 shadow-xs">
                <RefreshCw size={14} className="animate-spin text-[#10B981]" />
                <span className="text-xs">Nemotron is analyzing land parameters...</span>
              </div>
            </div>
          )}
        </div>

        {/* Input Footer */}
        <div className="p-4 bg-white border-t border-[#E3E9E3]">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            className="flex items-center gap-2"
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about carbon stock, soil health, verification..."
              className="cn-input flex-1 py-2.5 text-sm"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="btn-forest px-4 py-2.5 rounded-xl shrink-0"
            >
              <Send size={16} />
            </button>
          </form>

          <p className="text-[11px] text-gray-400 text-center mt-2.5">AI text is an interpretation, not a measurement, validated calculation, independent verification, or credit claim.</p>
        </div>
      </div>
    </div>
  );
};

export default AiAssistantDrawer;
