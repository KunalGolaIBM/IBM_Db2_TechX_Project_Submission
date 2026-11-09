import React, { useMemo } from 'react';
import { AreaChart, Area, ResponsiveContainer, YAxis } from 'recharts';

const SensorSparkline = ({ data, dataKey, color, label, value, unit, isPositiveGood = true }) => {
  
  // Format data for recharts if it's just an array of numbers
  const chartData = useMemo(() => {
    return data.map((val, i) => ({ index: i, [dataKey]: val }));
  }, [data, dataKey]);

  // Determine trend
  const first = data[0];
  const last = data[data.length - 1];
  const percentChange = ((last - first) / first) * 100;
  
  let isPositiveTrend = percentChange > 0;
  // If lower is better (e.g. CO2 ppm), invert the trend coloring logic
  let trendGood = isPositiveGood ? isPositiveTrend : !isPositiveTrend;
  
  const trendColor = Math.abs(percentChange) < 0.5 ? 'text-gray-400' : (trendGood ? 'text-emerald-400' : 'text-red-400');
  const arrow = Math.abs(percentChange) < 0.5 ? '→' : (isPositiveTrend ? '↗' : '↘');

  return (
    <div className="bg-dark-900 border border-carbon-800/40 rounded-xl p-4 flex flex-col h-full hover:border-carbon-700 transition-colors">
      <div className="flex justify-between items-start mb-2">
        <div>
          <p className="text-xs font-medium text-gray-500 mb-1">{label}</p>
          <div className="flex items-end gap-1">
            <h4 className="text-xl font-bold text-gray-200">{value}</h4>
            <span className="text-xs text-gray-500 mb-1">{unit}</span>
          </div>
        </div>
        <div className={`text-xs font-bold px-1.5 py-0.5 rounded-md bg-dark-800 border border-碳-800/50 ${trendColor} flex items-center gap-1`}>
          {arrow} {Math.abs(percentChange).toFixed(1)}%
        </div>
      </div>
      
      <div className="flex-1 mt-2 -mx-2 -mb-2">
        <ResponsiveContainer width="100%" height={60}>
          <AreaChart data={chartData}>
            <defs>
              <linearGradient id={`gradient-${dataKey}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={color} stopOpacity={0.3}/>
                <stop offset="95%" stopColor={color} stopOpacity={0}/>
              </linearGradient>
            </defs>
            <YAxis domain={['auto', 'auto']} hide />
            <Area 
              type="monotone" 
              dataKey={dataKey} 
              stroke={color} 
              strokeWidth={2}
              fillOpacity={1} 
              fill={`url(#gradient-${dataKey})`} 
              isAnimationActive={false} // Disable animation so interval updates don't stutter
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default SensorSparkline;
