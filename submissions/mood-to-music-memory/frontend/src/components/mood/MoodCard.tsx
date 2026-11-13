import React from 'react';
import { motion } from 'framer-motion';

interface MoodCardProps {
  mood: string;
  label: string;
  description: string;
  icon: React.ReactNode;
  color: string;
  glowColor: string;
  isSelected: boolean;
  onClick: () => void;
}

const MoodCard: React.FC<MoodCardProps> = ({
  mood,
  label,
  description,
  icon,
  color,
  glowColor,
  isSelected,
  onClick,
}) => {
  return (
    <motion.div
      whileHover={{ scale: 1.04 }}
      whileTap={{ scale: 0.98 }}
      onClick={onClick}
      style={{
        background: 'rgba(255,255,255,0.05)',
        border: isSelected ? `1px solid ${color}` : '1px solid rgba(255,255,255,0.1)',
        boxShadow: isSelected ? `0 0 20px ${glowColor}` : 'none',
        borderRadius: '1rem',
        padding: '14px 10px',
        cursor: 'pointer',
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '8px',
        transition: 'border 0.2s, box-shadow 0.2s',
        userSelect: 'none',
        minWidth: 0,
      }}
    >
      {/* Icon circle */}
      <div
        style={{
          width: 44,
          height: 44,
          borderRadius: '50%',
          background: `${color}22`,
          border: `1.5px solid ${color}55`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color,
          flexShrink: 0,
        }}
      >
        {icon}
      </div>

      {/* Label */}
      <span
        style={{
          fontWeight: 700,
          color: '#fff',
          fontSize: '0.85rem',
          letterSpacing: '0.01em',
          textAlign: 'center',
        }}
      >
        {label}
      </span>

      {/* Description */}
      <span
        style={{
          color: 'rgba(255,255,255,0.5)',
          fontSize: '0.68rem',
          textAlign: 'center',
          lineHeight: 1.35,
        }}
      >
        {description}
      </span>

      {/* Selected dot indicator */}
      {isSelected && (
        <div
          style={{
            width: 7,
            height: 7,
            borderRadius: '50%',
            background: color,
            boxShadow: `0 0 6px ${glowColor}`,
            marginTop: 2,
          }}
        />
      )}
    </motion.div>
  );
};

export default MoodCard;
