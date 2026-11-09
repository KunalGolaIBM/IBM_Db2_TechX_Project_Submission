import React from 'react';

export const CarbonNovaLogo = ({ className = '', size = 'md', light = false }) => {
  const iconSizes = {
    sm: 'w-6 h-6',
    md: 'w-8 h-8',
    lg: 'w-10 h-10',
    xl: 'w-12 h-12',
  };

  const textSizes = {
    sm: 'text-lg',
    md: 'text-xl',
    lg: 'text-2xl',
    xl: 'text-3xl',
  };

  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      {/* Botanical Leaf Mark matching the reference image */}
      <div className={`relative flex items-center justify-center ${iconSizes[size] || iconSizes.md}`}>
        <svg
          viewBox="0 0 40 40"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="w-full h-full drop-shadow-sm"
        >
          {/* Outer organic leaf curve */}
          <path
            d="M36 6C22 6 8 16 8 30C8 35.5 12.5 38 18 38C32 38 38 24 38 10C38 7.8 37.2 6 36 6Z"
            fill={light ? '#FFFFFF' : '#10B981'}
            fillOpacity={light ? '0.95' : '1'}
          />
          {/* Inner leaf vein negative space / stem */}
          <path
            d="M14 34C14 26 22 18 34 10C24 14 18 20 14 34Z"
            fill={light ? '#0C3327' : '#FFFFFF'}
          />
          <path
            d="M20 25C24 21 28 17 33 13"
            stroke={light ? '#0C3327' : '#FFFFFF'}
            strokeWidth="2"
            strokeLinecap="round"
          />
        </svg>
      </div>

      <div className="flex flex-col">
        <span
          className={`font-bold tracking-tight leading-none ${textSizes[size] || textSizes.md} ${
            light ? 'text-white' : 'text-[#0C3327]'
          }`}
        >
          Carbon<span className={light ? 'text-[#34D399]' : 'text-[#10B981]'}>Nova</span>
        </span>
      </div>
    </div>
  );
};

export default CarbonNovaLogo;
