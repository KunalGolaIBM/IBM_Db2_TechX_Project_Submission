import React, { useState, useEffect, useCallback } from 'react';
import { apiClient, Transaction } from '../../api/client';
import { formatDate, formatINR } from '../../utils/formatters';
import { 
  ArrowLeft, 
  Search, 
  Filter, 
  Clock, 
  CheckCircle2, 
  ArrowUpRight, 
  Store, 
  Loader2, 
  AlertCircle,
  RefreshCw,
  UploadCloud
} from 'lucide-react';

interface TransactionsViewProps {
  onBack: () => void;
  onImport?: () => void;
}

export const TransactionsView: React.FC<TransactionsViewProps> = ({ onBack, onImport }) => {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [debouncedSearch, setDebouncedSearch] = useState<string>('');
  const [offset, setOffset] = useState<number>(0);
  const [totalCount, setTotalCount] = useState<number>(0);
  const limit = 50;

  // Debounce search input by 300ms to avoid flooding queries while typing
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(searchQuery);
      setOffset(0); // Reset to first page when search changes
    }, 300);
    return () => clearTimeout(handler);
  }, [searchQuery]);

  const fetchTransactions = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await apiClient.dashboard.getTransactions({
        limit,
        offset,
        category: selectedCategory || undefined,
        search: debouncedSearch.trim() || undefined,
      });
      setTransactions(res.transactions);
      setTotalCount(res.total_count ?? res.count);
    } catch (err: any) {
      setError(err?.message || 'Failed to load transactions ledger from Db2.');
    } finally {
      setIsLoading(false);
    }
  }, [offset, selectedCategory, debouncedSearch]);

  useEffect(() => {
    fetchTransactions();
  }, [fetchTransactions]);

  return (
    <div className="space-y-6">
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 p-6 rounded-2xl border border-stone-200/80 dark:border-forest-900/60 bg-white dark:bg-[#10240d] shadow-sm">
        <div className="space-y-1">
          <button
            onClick={onBack}
            className="inline-flex items-center space-x-1.5 text-xs font-semibold text-sage-600 dark:text-sage-300 hover:text-forest-900 dark:hover:text-gold-400 transition-colors mb-1"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to Command Center</span>
          </button>
          <h2 className="text-xl font-bold tracking-tight text-forest-950 dark:text-cream-100">
            Full Transactions Ledger
          </h2>
          <p className="text-xs text-stone-500 dark:text-sage-400">
            Authenticated tenant records fetched directly from IBM Db2 <code className="font-mono text-forest-800 dark:text-gold-400">FINSIGHT.TRANSACTIONS</code>
          </p>
        </div>

        <div className="flex items-center space-x-2 self-start sm:self-auto">
          {onImport && (
            <button
              onClick={onImport}
              className="inline-flex items-center space-x-1.5 px-3.5 py-2 rounded-xl bg-[#15370D] hover:bg-[#1f4e14] text-white text-xs font-semibold shadow-xs transition-colors border border-forest-800"
            >
              <UploadCloud className="w-3.5 h-3.5 text-[#E5CD82]" />
              <span>Import CSV</span>
            </button>
          )}
          <button
            onClick={fetchTransactions}
            disabled={isLoading}
            className="inline-flex items-center space-x-1.5 px-3 py-2 rounded-xl border border-stone-200 dark:border-forest-800 hover:bg-stone-50 dark:hover:bg-forest-900/60 text-xs font-medium text-stone-700 dark:text-sage-300 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row gap-3">
        {/* Search Input */}
        <div className="relative flex-1">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-sage-500">
            <Search className="w-4 h-4" />
          </div>
          <input
            id="transaction-search-input"
            name="transaction_search"
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search merchant, description or category..."
            className="w-full pl-9 pr-3 py-2 text-xs rounded-xl border border-stone-200 dark:border-forest-800/80 bg-white dark:bg-[#10240d] text-forest-950 dark:text-cream-100 placeholder-stone-400 dark:placeholder-sage-500 focus:outline-hidden focus:ring-2 focus:ring-[#15370D] dark:focus:ring-[#E5CD82] transition-all shadow-xs"
          />
        </div>

        {/* Category Filter */}
        <div className="relative w-full sm:w-64">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-sage-500">
            <Filter className="w-3.5 h-3.5" />
          </div>
          <select
            id="transaction-category-filter"
            name="transaction_category"
            value={selectedCategory}
            onChange={(e) => {
              setSelectedCategory(e.target.value);
              setOffset(0);
            }}
            className="w-full pl-9 pr-8 py-2 text-xs rounded-xl border border-stone-200 dark:border-forest-800/80 bg-white dark:bg-[#10240d] text-forest-950 dark:text-cream-100 focus:outline-hidden focus:ring-2 focus:ring-[#15370D] dark:focus:ring-[#E5CD82] transition-all appearance-none shadow-xs"
          >
            <option value="">All Categories (Db2)</option>
            <option value="Groceries & Supermarket">Groceries & Supermarket</option>
            <option value="Dining & Restaurants">Dining & Restaurants</option>
            <option value="Home & Living">Home & Living</option>
            <option value="Transportation">Transportation</option>
            <option value="Utilities & Bills">Utilities & Bills</option>
            <option value="Entertainment & Subscriptions">Entertainment & Subscriptions</option>
            <option value="Salary & Professional">Salary & Professional</option>
            <option value="Investments & Trading">Investments & Trading</option>
          </select>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="p-4 rounded-xl border border-rose-200 dark:border-rose-900/60 bg-rose-50/80 dark:bg-rose-950/30 text-rose-800 dark:text-rose-300 text-xs flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Table / List View */}
      <div className="rounded-2xl border border-stone-200/80 dark:border-forest-900/60 bg-white dark:bg-[#10240d] shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="p-12 flex flex-col items-center justify-center space-y-3">
            <Loader2 className="w-6 h-6 animate-spin text-sage-500" />
            <span className="text-xs text-stone-500 dark:text-sage-400 font-mono">Querying IBM Db2 12.1.5.0...</span>
          </div>
        ) : transactions.length === 0 ? (
          <div className="p-12 text-center space-y-2">
            <p className="text-sm font-semibold text-forest-950 dark:text-cream-100">
              No transactions found
            </p>
            <p className="text-xs text-stone-500 dark:text-sage-400">
              Try adjusting your search criteria or category filter.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-stone-100 dark:border-forest-900/60 bg-stone-50/80 dark:bg-forest-900/40 text-stone-600 dark:text-sage-300 uppercase tracking-wider font-semibold text-[10px]">
                  <th className="py-3 px-4">Date</th>
                  <th className="py-3 px-4">Merchant / Payee</th>
                  <th className="py-3 px-4">Category</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Amount</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-100 dark:divide-forest-900/50">
                {transactions.map((tx: Transaction) => {
                  const isCredit = tx.transaction_type === 'CREDIT';
                  const isPending = tx.status === 'PENDING';

                  return (
                    <tr
                      key={tx.transaction_id}
                      className="hover:bg-stone-50/60 dark:hover:bg-forest-900/30 transition-colors"
                    >
                      {/* Date */}
                      <td className="py-3.5 px-4 font-mono text-stone-500 dark:text-sage-400 whitespace-nowrap">
                        {formatDate(tx.transaction_date)}
                      </td>

                      {/* Merchant */}
                      <td className="py-3.5 px-4 font-medium text-stone-900 dark:text-cream-100">
                        <div className="flex items-center space-x-2.5">
                          <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 border ${
                            isCredit
                              ? 'bg-forest-50 dark:bg-forest-900/80 text-forest-700 dark:text-forest-300 border-forest-200 dark:border-forest-700/60'
                              : 'bg-stone-100 dark:bg-[#163013] text-stone-600 dark:text-sage-300 border-stone-200/60 dark:border-forest-800/60'
                          }`}>
                            {isCredit ? <ArrowUpRight className="w-3.5 h-3.5" /> : <Store className="w-3.5 h-3.5" />}
                          </div>
                          <div>
                            <div className="font-semibold text-forest-950 dark:text-cream-100">
                              {tx.merchant}
                            </div>
                            {tx.description && (
                              <div className="text-[11px] text-stone-400 dark:text-sage-400 font-normal max-w-xs truncate">
                                {tx.description}
                              </div>
                            )}
                          </div>
                        </div>
                      </td>

                      {/* Category */}
                      <td className="py-3.5 px-4 text-stone-600 dark:text-sage-400">
                        <span className="inline-block px-2 py-0.5 rounded-md text-[11px] bg-stone-100 dark:bg-forest-900/60 text-stone-700 dark:text-sage-300 border border-stone-200/60 dark:border-forest-800/60 font-medium">
                          {tx.category_name}
                        </span>
                      </td>

                      {/* Status */}
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        {isPending ? (
                          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#FFF2B4] text-[#15370D] border border-[#E5CD82]">
                            <Clock className="w-2.5 h-2.5 text-[#15370D]" />
                            <span>Pending</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-sage-100/70 dark:bg-sage-950/60 text-sage-800 dark:text-sage-300 border border-sage-200/70 dark:border-sage-800/60">
                            <CheckCircle2 className="w-2.5 h-2.5 text-sage-600 dark:text-sage-400" />
                            <span>Posted</span>
                          </span>
                        )}
                      </td>

                      {/* Amount */}
                      <td className="py-3.5 px-4 text-right whitespace-nowrap font-mono font-bold">
                        <span className={isCredit ? 'text-forest-700 dark:text-forest-400' : 'text-stone-900 dark:text-cream-100'}>
                          {isCredit ? `+${formatINR(tx.amount)}` : `-${formatINR(tx.amount)}`}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination & Count Bar */}
        <div className="p-4 border-t border-stone-100 dark:border-forest-900/60 flex items-center justify-between text-xs text-stone-500 dark:text-sage-400">
          <span>
            Showing{' '}
            <strong className="text-forest-950 dark:text-cream-100 font-mono">
              {transactions.length > 0 ? offset + 1 : 0} – {Math.min(offset + transactions.length, totalCount)}
            </strong>{' '}
            of <strong className="text-forest-950 dark:text-cream-100 font-mono">{totalCount}</strong> matching records
          </span>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setOffset(Math.max(offset - limit, 0))}
              disabled={offset === 0 || isLoading}
              className="px-3 py-1 rounded-lg border border-stone-200 dark:border-forest-800 disabled:opacity-40 hover:bg-stone-50 dark:hover:bg-forest-900/60 text-stone-700 dark:text-sage-300"
            >
              Previous
            </button>
            <button
              onClick={() => setOffset(offset + limit)}
              disabled={offset + limit >= totalCount || isLoading}
              className="px-3 py-1 rounded-lg border border-stone-200 dark:border-forest-800 disabled:opacity-40 hover:bg-stone-50 dark:hover:bg-forest-900/60 text-stone-700 dark:text-sage-300"
            >
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
