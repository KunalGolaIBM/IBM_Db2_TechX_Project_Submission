import React from 'react';
import { Leaf, AlertTriangle, CheckCircle, Flame } from 'lucide-react';
import { motion } from 'framer-motion';

const LiveQualityBadge = ({ score, tier, lastUpdate }) => {
  let config = {
    color: 'bg-carbon-900',
    text: 'text-gray-400',
    border: 'border-carbon-800',
    icon: Leaf,
    label: 'Standard',
  };

  if (tier === 'gold') {
    config = {
      color: 'bg-amber-400/10',
      text: 'text-amber-400',
      border: 'border-amber-400/30',
      icon: Flame,
      label: 'Premium',
    };
  } else if (tier === 'silver') {
    config = {
      color: 'bg-slate-400/10',
      text: 'text-slate-300',
      border: 'border-slate-400/30',
      icon: CheckCircle,
      label: 'Standard',
    };
  } else if (tier === 'bronze') {
    config = {
      color: 'bg-orange-400/10',
      text: 'text-orange-400',
      border: 'border-orange-400/30',
      icon: CheckCircle,
      label: 'Basic',
    };
  } else if (tier === 'flagged') {
    config = {
      color: 'bg-red-500/10',
      text: 'text-red-400',
      border: 'border-red-500/30',
      icon: AlertTriangle,
      label: 'Flagged',
    };
  }

  const Icon = config.icon;

  return (
    <motion.div 
      key={lastUpdate} // Triggers animation on change
      initial={{ scale: 1.1, filter: 'brightness(1.5)' }}
      animate={{ scale: 1, filter: 'brightness(1)' }}
      transition={{ duration: 0.5 }}
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold border ${config.color} ${config.text} ${config.border}`}
      title={`Live Score: ${score}/100`}
    >
      <Icon size={12} className={tier === 'gold' ? 'animate-pulse' : ''} />
      <span>{score} • {config.label}</span>
      <span className="live-dot ml-1 w-1.5 h-1.5" />
    </motion.div>
  );
};

export default LiveQualityBadge;
