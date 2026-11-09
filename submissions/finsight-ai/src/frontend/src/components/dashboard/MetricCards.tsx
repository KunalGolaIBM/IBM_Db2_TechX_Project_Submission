import React from 'react';
import { ArrowUpRight, ArrowDownRight, Wallet, Layers } from 'lucide-react';
import { formatINR } from '../../utils/formatters';
import { DashboardSummary } from '../../api/client';

interface MetricCardsProps {
  summary: DashboardSummary | null;
  isLoading: boolean;
}

export const MetricCards: React.FC<MetricCardsProps> = ({ summary, isLoading }) => {
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="p-5 rounded-2xl border border-[#E6E2D8] dark:border-[#1c3619] bg-white dark:bg-[#10210e] animate-pulse space-y-3"
          >
            <div className="flex items-center justify-between">
              <div className="h-3.5 bg-[#E6E2D8] dark:bg-[#1c3619] rounded w-24"></div>
              <div className="w-8 h-8 rounded-lg bg-[#E6E2D8] dark:bg-[#1c3619]"></div>
            </div>
            <div className="h-7 bg-[#E6E2D8] dark:bg-[#1c3619] rounded w-36"></div>
            <div className="h-3 bg-[#FAF8F3] dark:bg-[#162a14] rounded w-28"></div>
          </div>
        ))}
      </div>
    );
  }

  const income = summary?.total_income ?? 0;
  const expenses = summary?.total_expenses ?? 0;
  const netSavings = summary?.net_savings ?? 0;
  const txCount = summary?.total_transactions ?? 0;
  const isNetPositive = netSavings >= 0;
  const savingsRate = income > 0 ? ((netSavings / income) * 100).toFixed(1) : '0.0';

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* 1. Total Inflow */}
      <div className="p-5 rounded-2xl border border-[#E6E2D8] dark:border-[#1c3619] bg-white dark:bg-[#10210e] shadow-2xs hover:border-[#728E6D]/50 dark:hover:border-[#2b5426] transition-colors">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-[#5C6C58] dark:text-[#95A890]">
            Total Inflow
          </span>
          <div className="w-8 h-8 rounded-xl bg-[#e3ece0] dark:bg-[#183612] text-[#15370D] dark:text-[#E5CD82] border border-[#728E6D]/20 flex items-center justify-center">
            <ArrowUpRight className="w-4 h-4" />
          </div>
        </div>
        <div className="mt-3">
          <div className="text-2xl font-extrabold tracking-tight text-[#152912] dark:text-white font-sans">
            {formatINR(income)}
          </div>
          <div className="mt-1 flex items-center space-x-1.5 text-[11px] text-[#728E6D] dark:text-[#A3B89E] font-medium">
            <span className="font-semibold">Posted credits</span>
            <span className="text-[#C5BEAF]">·</span>
            <span className="text-[#5C6C58] dark:text-[#95A890]">Jun – Nov 2026</span>
          </div>
        </div>
      </div>

      {/* 2. Total Outflow */}
      <div className="p-5 rounded-2xl border border-[#E6E2D8] dark:border-[#1c3619] bg-white dark:bg-[#10210e] shadow-2xs hover:border-[#728E6D]/50 dark:hover:border-[#2b5426] transition-colors">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-[#5C6C58] dark:text-[#95A890]">
            Total Outflow
          </span>
          <div className="w-8 h-8 rounded-xl bg-[#FAF0ED] dark:bg-[#281513] text-[#A85C53] dark:text-[#E8998D] border border-[#A85C53]/20 flex items-center justify-center">
            <ArrowDownRight className="w-4 h-4" />
          </div>
        </div>
        <div className="mt-3">
          <div className="text-2xl font-extrabold tracking-tight text-[#152912] dark:text-white font-sans">
            {formatINR(expenses)}
          </div>
          <div className="mt-1 flex items-center space-x-1.5 text-[11px] text-[#5C6C58] dark:text-[#95A890]">
            <span className="font-semibold text-[#A85C53] dark:text-[#E8998D]">Excludes transfers</span>
            <span className="text-[#C5BEAF]">·</span>
            <span>Posted debits</span>
          </div>
        </div>
      </div>

      {/* 3. Net Cash Flow */}
      <div className="p-5 rounded-2xl border border-[#E6E2D8] dark:border-[#1c3619] bg-white dark:bg-[#10210e] shadow-2xs hover:border-[#E5CD82]/60 dark:hover:border-[#E5CD82]/40 transition-colors">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-[#5C6C58] dark:text-[#95A890]">
            Net Cash Flow
          </span>
          <div className="w-8 h-8 rounded-xl bg-[#FFF2B4] dark:bg-[#1e3c15] text-[#15370D] dark:text-[#E5CD82] border border-[#E5CD82]/40 flex items-center justify-center">
            <Wallet className="w-4 h-4" />
          </div>
        </div>
        <div className="mt-3">
          <div className="text-2xl font-extrabold tracking-tight text-[#15370D] dark:text-[#E5CD82] font-sans">
            {formatINR(netSavings)}
          </div>
          <div className="mt-1 flex items-center space-x-1.5 text-[11px]">
            <span className="px-1.5 py-0.5 rounded-md font-bold bg-[#FFF2B4] dark:bg-[#234219] text-[#15370D] dark:text-[#FFF2B4] border border-[#E5CD82]/40 text-[10px]">
              {isNetPositive ? `+${savingsRate}% Surplus` : `${savingsRate}% Deficit`}
            </span>
            <span className="text-[#C5BEAF]">·</span>
            <span className="text-[#5C6C58] dark:text-[#95A890]">Net Savings</span>
          </div>
        </div>
      </div>

      {/* 4. Total Transactions */}
      <div className="p-5 rounded-2xl border border-[#E6E2D8] dark:border-[#1c3619] bg-white dark:bg-[#10210e] shadow-2xs hover:border-[#728E6D]/50 dark:hover:border-[#2b5426] transition-colors">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-[#5C6C58] dark:text-[#95A890]">
            Total Transactions
          </span>
          <div className="w-8 h-8 rounded-xl bg-[#e8ede6] dark:bg-[#182c16] text-[#728E6D] dark:text-[#A3B89E] border border-[#728E6D]/20 flex items-center justify-center">
            <Layers className="w-4 h-4" />
          </div>
        </div>
        <div className="mt-3">
          <div className="text-2xl font-extrabold tracking-tight text-[#152912] dark:text-white font-sans">
            {txCount}
          </div>
          <div className="mt-1 flex items-center space-x-1.5 text-[11px] text-[#5C6C58] dark:text-[#95A890]">
            <span className="font-semibold text-[#15370D] dark:text-[#E5CD82]">202 Posted</span>
            <span className="text-[#C5BEAF]">·</span>
            <span className="px-1 py-0.2 rounded bg-[#FFF2B4] dark:bg-[#25391d] text-[#15370D] dark:text-[#E5CD82] font-semibold text-[10px]">
              6 Pending
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
