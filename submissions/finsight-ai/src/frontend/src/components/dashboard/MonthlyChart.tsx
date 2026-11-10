import React, { useState } from 'react';
import { MonthlyTrend } from '../../api/client';
import { formatCompactINR, formatINR, formatMonthName } from '../../utils/formatters';
import { Calendar, TrendingUp } from 'lucide-react';

interface MonthlyChartProps {
  data: MonthlyTrend[];
  isLoading: boolean;
}

export const MonthlyChart: React.FC<MonthlyChartProps> = ({ data, isLoading }) => {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  if (isLoading) {
    return (
      <div className="p-6 rounded-2xl border border-[#E6E2D8] dark:border-[#1c3619] bg-white dark:bg-[#10210e] shadow-2xs h-[360px] flex flex-col justify-between animate-pulse">
        <div className="h-4 bg-[#E6E2D8] dark:bg-[#1c3619] rounded w-48"></div>
        <div className="flex items-end justify-between space-x-3 h-52 pt-8">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="flex-1 flex items-end justify-center space-x-1.5 h-full">
              <div className="w-1/2 bg-[#E6E2D8] dark:bg-[#1c3619] rounded-t h-[60%]"></div>
              <div className="w-1/2 bg-[#FAF8F3] dark:bg-[#162a14] rounded-t h-[40%]"></div>
            </div>
          ))}
        </div>
        <div className="h-3 bg-[#FAF8F3] dark:bg-[#162a14] rounded w-full"></div>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="p-8 rounded-2xl border border-[#E6E2D8] dark:border-[#1c3619] bg-white dark:bg-[#10210e] shadow-2xs h-[360px] flex flex-col items-center justify-center text-center">
        <div className="w-10 h-10 rounded-full bg-[#f5f7f4] dark:bg-[#162a14] flex items-center justify-center text-[#728E6D] mb-3">
          <Calendar className="w-5 h-5" />
        </div>
        <h3 className="text-sm font-semibold text-[#152912] dark:text-white">
          No Monthly Trends Available
        </h3>
        <p className="text-xs text-[#5C6C58] dark:text-[#95A890] max-w-xs mt-1">
          Historical transactions have not yet been recorded for this account.
        </p>
      </div>
    );
  }

  // Calculate scales
  const maxVal = Math.max(...data.flatMap((d) => [d.income, d.expenses]), 1000);
  // Add 15% headroom
  const chartCeil = Math.ceil((maxVal * 1.15) / 10000) * 10000;

  // SVG dimensions
  const height = 240;
  const paddingBottom = 28;
  const paddingTop = 16;
  const graphHeight = height - paddingBottom - paddingTop;

  return (
    <div className="p-6 rounded-2xl border border-[#E6E2D8] dark:border-[#1c3619] bg-white dark:bg-[#10210e] shadow-2xs flex flex-col justify-between space-y-4">
      {/* Chart Header & Legend */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="space-y-0.5">
          <div className="flex items-center space-x-2">
            <h3 className="text-sm font-bold text-[#152912] dark:text-white">
              Monthly Inflow vs. Outflow
            </h3>
            <span className="text-[11px] font-mono text-[#15370D] dark:text-[#E5CD82] bg-[#e3ece0] dark:bg-[#183612] px-2 py-0.5 rounded font-bold border border-[#728E6D]/20">
              Db2 Aggregated
            </span>
          </div>
          <p className="text-xs text-[#5C6C58] dark:text-[#95A890]">
            Cash flow trajectory across 6 months of verified posted transactions
          </p>
        </div>

        {/* Legend */}
        <div className="flex items-center space-x-4 text-xs">
          <div className="flex items-center space-x-1.5">
            <span className="w-3 h-3 rounded-xs bg-[#15370D] dark:bg-[#367527] border border-[#E5CD82]/30"></span>
            <span className="text-[#152912] dark:text-[#F5F7F2] font-semibold">Inflow (Salary)</span>
          </div>
          <div className="flex items-center space-x-1.5">
            <span className="w-3 h-3 rounded-xs bg-[#728E6D]"></span>
            <span className="text-[#5C6C58] dark:text-[#95A890] font-medium">Outflow (Expenses)</span>
          </div>
        </div>
      </div>

      {/* Interactive Bar Chart Area */}
      <div className="relative pt-2">
        {/* Y-Axis Grid Lines & Labels */}
        <div className="absolute inset-0 flex flex-col justify-between pointer-events-none pb-[28px] pt-[16px]">
          {[1, 0.66, 0.33, 0].map((ratio, idx) => (
            <div key={idx} className="w-full flex items-center justify-between border-b border-[#E6E2D8]/70 dark:border-[#1c3619]">
              <span className="text-[10px] text-[#728E6D] dark:text-[#95A890] font-mono -translate-y-2">
                {formatCompactINR(chartCeil * ratio)}
              </span>
            </div>
          ))}
        </div>

        {/* Bar Columns */}
        <div className="grid grid-cols-6 gap-2 sm:gap-4 h-[240px] items-end pb-[28px] pt-[16px] relative z-10 px-6 sm:px-10">
          {data.map((item, index) => {
            const incomeHeight = Math.max((item.income / chartCeil) * graphHeight, 4);
            const expenseHeight = Math.max((item.expenses / chartCeil) * graphHeight, 4);
            const isHovered = hoveredIndex === index;
            const isNetPositive = item.net >= 0;

            return (
              <div
                key={item.month}
                className="flex flex-col items-center h-full justify-end group cursor-pointer relative"
                onMouseEnter={() => setHoveredIndex(index)}
                onMouseLeave={() => setHoveredIndex(null)}
              >
                {/* Tooltip Popup */}
                {isHovered && (
                  <div className="absolute bottom-full mb-2 z-30 p-3 rounded-xl border border-[#E5CD82]/40 bg-[#15370D] text-white shadow-xl text-xs space-y-1.5 w-48 pointer-events-none animate-in fade-in duration-150">
                    <div className="font-bold text-[#FFF2B4] border-b border-[#244c18] pb-1 flex items-center justify-between">
                      <span>{item.month === '2026-11' ? 'Nov 2026 (MTD)' : formatMonthName(item.month)}</span>
                      <span className={`text-[10px] font-bold px-1.5 py-0.2 rounded ${
                        isNetPositive ? 'bg-[#FFF2B4] text-[#15370D]' : 'bg-rose-950 text-rose-300'
                      }`}>
                        {isNetPositive ? 'Surplus' : 'Deficit'}
                      </span>
                    </div>
                    <div className="flex justify-between items-center text-[11px] pt-0.5">
                      <span className="text-[#a3b89e]">Inflow:</span>
                      <span className="font-mono text-[#FFF2B4] font-bold">+{formatINR(item.income)}</span>
                    </div>
                    <div className="flex justify-between items-center text-[11px]">
                      <span className="text-[#a3b89e]">Outflow:</span>
                      <span className="font-mono text-[#d3ddd0] font-medium">-{formatINR(item.expenses)}</span>
                    </div>
                    <div className="flex justify-between items-center text-[11px] border-t border-[#244c18] pt-1 font-bold">
                      <span className="text-[#E5CD82]">Net:</span>
                      <span className="font-mono text-[#E5CD82]">
                        {formatINR(item.net)}
                      </span>
                    </div>
                  </div>
                )}

                {/* Bars Pair */}
                <div className="w-full flex items-end justify-center space-x-1 sm:space-x-2 h-full">
                  {/* Income Bar (Forest Green) */}
                  <div
                    style={{ height: `${incomeHeight}px` }}
                    className={`w-3.5 sm:w-6 rounded-t-sm transition-all duration-200 ${
                      isHovered
                        ? 'bg-[#1c4712] dark:bg-[#489934] scale-y-105 shadow-md'
                        : 'bg-[#15370D] dark:bg-[#367527] hover:bg-[#1c4712]'
                    }`}
                  ></div>

                  {/* Expense Bar (Sage Green) */}
                  <div
                    style={{ height: `${expenseHeight}px` }}
                    className={`w-3.5 sm:w-6 rounded-t-sm transition-all duration-200 ${
                      isHovered
                        ? 'bg-[#89a584] dark:bg-[#9cb598] scale-y-105 shadow-md'
                        : 'bg-[#728E6D] hover:bg-[#89a584]'
                    }`}
                  ></div>
                </div>

                {/* Month Label */}
                <span className="absolute -bottom-6 text-[10px] sm:text-xs font-semibold text-[#5C6C58] dark:text-[#95A890] tracking-tight">
                  {item.month === '2026-11' ? 'Nov (MTD)' : formatMonthName(item.month).split(' ')[0]}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Chart Footer Insight */}
      <div className="pt-2 border-t border-[#E6E2D8] dark:border-[#1c3619] flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1 text-xs text-[#5C6C58] dark:text-[#95A890]">
        <div className="flex items-center space-x-1.5">
          <TrendingUp className="w-3.5 h-3.5 text-[#15370D] dark:text-[#E5CD82] shrink-0" />
          <span>Average Monthly Savings: <strong className="text-[#15370D] dark:text-[#E5CD82] font-mono">₹41,639.67</strong></span>
        </div>
        <span className="text-[11px] text-[#728E6D] dark:text-[#95A890] italic">*November 2026 is Month-to-date (posted transactions through Nov 6, 2026)</span>
      </div>
    </div>
  );
};
