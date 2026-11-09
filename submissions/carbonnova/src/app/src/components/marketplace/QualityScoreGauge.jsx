import React from 'react';
import { motion } from 'framer-motion';

const QualityScoreGauge = ({ score, size = 200, strokeWidth = 15 }) => {
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (score / 100) * circumference;

  let color = '#ef4444'; // Red for flagged
  let glowColor = 'rgba(239, 68, 68, 0.4)';
  if (score >= 85) {
    color = '#fbbf24'; // Gold
    glowColor = 'rgba(251, 191, 36, 0.4)';
  } else if (score >= 65) {
    color = '#94a3b8'; // Silver
    glowColor = 'rgba(148, 163, 184, 0.4)';
  } else if (score >= 45) {
    color = '#ea580c'; // Bronze
    glowColor = 'rgba(234, 88, 12, 0.4)';
  }

  return (
    <div className="relative flex items-center justify-center font-sans tracking-tight" style={{ width: size, height: size }}>
      
      {/* Background track */}
      <svg width={size} height={size} className="transform -rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#1d3025" // dark-700 approx
          strokeWidth={strokeWidth}
          className="transition-all duration-300"
        />
        
        {/* Animated fill */}
        <motion.circle
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1, ease: "easeOut" }}
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeLinecap="round"
          style={{ filter: `drop-shadow(0 0 8px ${glowColor})` }}
        />
      </svg>
      
      {/* Score text */}
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <motion.span 
          key={score}
          initial={{ scale: 1.2, opacity: 0.5 }}
          animate={{ scale: 1, opacity: 1 }}
          className="text-4xl font-black text-white"
        >
          {score}
        </motion.span>
        <span className="text-xs font-semibold uppercase tracking-widest text-gray-500 mt-1">Score</span>
      </div>
      
    </div>
  );
};

export default QualityScoreGauge;
