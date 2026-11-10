import React from 'react';
import { CategorySpending } from '../../api/client';
import { formatINR } from '../../utils/formatters';
import { PieChart, ShoppingBag } from 'lucide-react';

interface CategoryBreakdownProps {
  categories: CategorySpending[];
  totalExpenses: number;
  isLoading: boolean;
}

export const CategoryBreakdown: React.FC<CategoryBreakdownProps> = ({
  categories,
  totalExpenses,
  isLoading,
}) => {
  if (isLoading) {
    return (
      <div className="p-6 rounded-2xl border border-[#E6E2D8] dark:border-[#1c3619] bg-white dark:bg-[#10210e] shadow-2xs h-full flex flex-col justify-between animate-pulse">
        <div className="h-4 bg-[#E6E2D8] dark:bg-[#1c3619] rounded w-40"></div>
        <div className="space-y-4 my-4">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="space-y-1.5">
              <div className="flex justify-between">
                <div className="h-3 bg-[#E6E2D8] dark:bg-[#1c3619] rounded w-24"></div>
                <div className="h-3 bg-[#E6E2D8] dark:bg-[#1c3619] rounded w-16"></div>
              </div>
              <div className="h-2 bg-[#FAF8F3] dark:bg-[#162a14] rounded w-full"></div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (!categories || categories.length === 0) {
    return (
      <div className="p-8 rounded-2xl border border-[#E6E2D8] dark:border-[#1c3619] bg-white dark:bg-[#10210e] shadow-2xs h-full flex flex-col items-center justify-center text-center">
        <div className="w-10 h-10 rounded-full bg-[#f5f7f4] dark:bg-[#162a14] flex items-center justify-center text-[#728E6D] mb-3">
          <ShoppingBag className="w-5 h-5" />
        </div>
        <h3 className="text-sm font-semibold text-[#152912] dark:text-white">
          No Category Data Available
        </h3>
        <p className="text-xs text-[#5C6C58] dark:text-[#95A890] max-w-xs mt-1">
          Categorized expenses will appear once transactions are recorded.
        </p>
      </div>
    );
  }

  // FinSight Brand Palette Bar Colors
  const barColors = [
    'bg-[#15370D] dark:bg-[#489934]', // Forest Green
    'bg-[#728E6D]',                   // Sage Green
    'bg-[#D4B760] dark:bg-[#E5CD82]', // Muted Gold
    'bg-[#587554]',                   // Deep Sage
    'bg-[#A48238] dark:bg-[#e0c476]', // Antique Gold
    'bg-[#8FA789]',                   // Pale Sage
  ];

  const dotColors = [
    'bg-[#15370D] dark:bg-[#489934]',
    'bg-[#728E6D]',
    'bg-[#D4B760] dark:bg-[#E5CD82]',
    'bg-[#587554]',
    'bg-[#A48238] dark:bg-[#e0c476]',
    'bg-[#8FA789]',
  ];

  const effectiveTotal = totalExpenses > 0 ? totalExpenses : 1;

  return (
    <div className="p-6 rounded-2xl border border-[#E6E2D8] dark:border-[#1c3619] bg-white dark:bg-[#10210e] shadow-2xs flex flex-col justify-between space-y-4">
      {/* Header */}
      <div className="space-y-0.5">
        <div className="flex items-center space-x-2">
          <PieChart className="w-4 h-4 text-[#728E6D] dark:text-[#E5CD82]" />
          <h3 className="text-sm font-bold text-[#152912] dark:text-white">
            Top Spending by Category
          </h3>
        </div>
        <p className="text-xs text-[#5C6C58] dark:text-[#95A890]">
          Distribution across highest expenditure sectors
        </p>
      </div>

      {/* Category Progress Bars */}
      <div className="space-y-3.5 pt-1">
        {categories.map((cat, idx) => {
          const percentage = ((cat.total_spent / effectiveTotal) * 100).toFixed(1);
          const colorClass = barColors[idx % barColors.length];
          const dotColor = dotColors[idx % dotColors.length];

          return (
            <div key={cat.category} className="space-y-1.5 group">
              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center space-x-2">
                  <span className={`w-2 h-2 rounded-full ${dotColor}`}></span>
                  <span className="font-semibold text-[#152912] dark:text-[#F5F7F2] truncate max-w-[150px] sm:max-w-[200px]">
                    {cat.category}
                  </span>
                  <span className="text-[11px] text-[#728E6D] dark:text-[#95A890] font-mono">
                    ({cat.count} txs)
                  </span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="font-mono font-bold text-[#152912] dark:text-white">
                    {formatINR(cat.total_spent)}
                  </span>
                  <span className="text-[11px] font-mono text-[#5C6C58] dark:text-[#95A890] w-12 text-right">
                    {percentage}%
                  </span>
                </div>
              </div>

              {/* Progress Track */}
              <div className="w-full bg-[#f0ebe0] dark:bg-[#182c16] h-1.5 rounded-full overflow-hidden">
                <div
                  style={{ width: `${Math.min(parseFloat(percentage), 100)}%` }}
                  className={`h-full rounded-full transition-all duration-300 ${colorClass}`}
                ></div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Footer Total */}
      <div className="pt-3 border-t border-[#E6E2D8] dark:border-[#1c3619] flex items-center justify-between text-xs">
        <span className="text-[#5C6C58] dark:text-[#95A890] font-medium">Top 6 Sectors:</span>
        <span className="font-mono font-bold text-[#15370D] dark:text-[#E5CD82]">
          {formatINR(categories.reduce((acc, c) => acc + c.total_spent, 0))}
        </span>
      </div>
    </div>
  );
};
