import React from 'react';
import { Transaction } from '../../api/client';
import { formatDate, formatINR } from '../../utils/formatters';
import { 
  ArrowUpRight, 
  Clock, 
  CheckCircle2, 
  ArrowRight,
  Receipt,
  Store
} from 'lucide-react';

interface RecentTransactionsProps {
  transactions: Transaction[];
  isLoading: boolean;
  onViewAll: () => void;
}

export const RecentTransactions: React.FC<RecentTransactionsProps> = ({
  transactions,
  isLoading,
  onViewAll,
}) => {
  if (isLoading) {
    return (
      <div className="p-6 rounded-2xl border border-stone-200/80 dark:border-forest-900/60 bg-white dark:bg-[#10240d] shadow-sm space-y-4 animate-pulse">
        <div className="flex justify-between items-center">
          <div className="h-4 bg-stone-200 dark:bg-forest-900/60 rounded w-44"></div>
          <div className="h-4 bg-stone-200 dark:bg-forest-900/60 rounded w-24"></div>
        </div>
        <div className="space-y-3 pt-2">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-14 bg-stone-100 dark:bg-forest-900/30 rounded-xl"></div>
          ))}
        </div>
      </div>
    );
  }

  if (!transactions || transactions.length === 0) {
    return (
      <div className="p-8 rounded-2xl border border-stone-200/80 dark:border-forest-900/60 bg-white dark:bg-[#10240d] shadow-sm flex flex-col items-center justify-center text-center">
        <div className="w-10 h-10 rounded-full bg-cream-100 dark:bg-forest-900/70 flex items-center justify-center text-sage-600 dark:text-sage-300 mb-3">
          <Receipt className="w-5 h-5" />
        </div>
        <h3 className="text-sm font-semibold text-forest-950 dark:text-cream-100">
          No Recent Transactions
        </h3>
        <p className="text-xs text-stone-500 dark:text-sage-400 max-w-sm mt-1">
          Your transaction ledger is empty. Incoming bank credits and debits will appear here.
        </p>
      </div>
    );
  }

  return (
    <div className="p-6 rounded-2xl border border-stone-200/80 dark:border-forest-900/60 bg-white dark:bg-[#10240d] shadow-sm space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        <div className="space-y-0.5">
          <div className="flex items-center space-x-2">
            <h3 className="text-sm font-bold text-forest-950 dark:text-cream-100 tracking-tight">
              Recent Financial Activity
            </h3>
            <span className="text-[11px] font-mono text-sage-700 dark:text-sage-300 bg-sage-50 dark:bg-forest-900/50 px-2 py-0.5 rounded border border-sage-200/70 dark:border-forest-800/80">
              Latest {transactions.length}
            </span>
          </div>
          <p className="text-xs text-stone-500 dark:text-sage-400">
            Real-time ledger updates from IBM Db2
          </p>
        </div>

        <button
          onClick={onViewAll}
          className="inline-flex items-center space-x-1 text-xs font-semibold text-forest-800 hover:text-forest-950 dark:text-gold-400 dark:hover:text-gold-300 transition-colors"
        >
          <span>View all transactions</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Transaction List */}
      <div className="divide-y divide-stone-100 dark:divide-forest-900/50">
        {transactions.map((tx) => {
          const isCredit = tx.transaction_type === 'CREDIT';
          const isPending = tx.status === 'PENDING';

          return (
            <div
              key={tx.transaction_id}
              className="py-3.5 first:pt-2 last:pb-1 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 hover:bg-stone-50/70 dark:hover:bg-forest-900/30 px-2 -mx-2 rounded-xl transition-colors"
            >
              {/* Left: Merchant, Category & Date */}
              <div className="flex items-start space-x-3 min-w-0">
                <div className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 mt-0.5 border ${
                  isCredit
                    ? 'bg-forest-50 dark:bg-forest-900/80 text-forest-700 dark:text-forest-300 border-forest-200 dark:border-forest-700/60'
                    : 'bg-stone-100 dark:bg-[#163013] text-stone-700 dark:text-sage-200 border-stone-200/60 dark:border-forest-800/60'
                }`}>
                  {isCredit ? (
                    <ArrowUpRight className="w-4 h-4" />
                  ) : (
                    <Store className="w-4 h-4" />
                  )}
                </div>

                <div className="min-w-0 flex-1">
                  <div className="flex items-center space-x-2">
                    <span className="text-xs font-semibold text-forest-950 dark:text-cream-100 truncate">
                      {tx.merchant}
                    </span>
                    {/* Status Badge */}
                    {isPending ? (
                      <span className="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded text-[10px] font-bold bg-[#FFF2B4] text-[#15370D] border border-[#E5CD82]">
                        <Clock className="w-2.5 h-2.5 text-[#15370D]" />
                        <span>Pending</span>
                      </span>
                    ) : (
                      <span className="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-sage-100/70 dark:bg-sage-950/60 text-sage-800 dark:text-sage-300 border border-sage-200/70 dark:border-sage-800/60">
                        <CheckCircle2 className="w-2.5 h-2.5 text-sage-600 dark:text-sage-400" />
                        <span>Posted</span>
                      </span>
                    )}
                  </div>

                  <div className="flex items-center space-x-2 text-[11px] text-stone-500 dark:text-sage-400 mt-0.5">
                    <span className="truncate">{tx.category_name}</span>
                    <span className="text-stone-300 dark:text-forest-800">·</span>
                    <span className="shrink-0">{formatDate(tx.transaction_date)}</span>
                  </div>
                </div>
              </div>

              {/* Right: Amount & Type */}
              <div className="flex sm:flex-col items-center sm:items-end justify-between sm:justify-center pl-12 sm:pl-0">
                <div className={`font-mono text-xs sm:text-sm font-bold ${
                  isCredit
                    ? 'text-forest-700 dark:text-forest-400'
                    : 'text-stone-900 dark:text-cream-100'
                }`}>
                  {isCredit ? `+${formatINR(tx.amount)}` : `-${formatINR(tx.amount)}`}
                </div>
                <span className="text-[10px] uppercase font-mono tracking-wider text-sage-500 dark:text-sage-400">
                  {tx.transaction_type}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Footer */}
      <div className="pt-2 border-t border-stone-100 dark:border-forest-900/50 flex items-center justify-between text-xs text-stone-500 dark:text-sage-400">
        <span>Verified against Db2 <code className="font-mono text-stone-700 dark:text-sage-300">FINSIGHT.TRANSACTIONS</code></span>
        <button
          onClick={onViewAll}
          className="font-medium text-forest-800 dark:text-gold-400 hover:underline"
        >
          Explore All Transactions
        </button>
      </div>
    </div>
  );
};
