import React, { useState } from 'react';
import {
  Search,
  Sparkles,
  Database,
  Loader2,
  AlertCircle,
  Tag,
  Calendar,
  CheckCircle2,
  Clock,
  ArrowRight,
  SlidersHorizontal,
  Info
} from 'lucide-react';
import { apiClient, SearchResultItem } from '../../api/client';
import { useAuth } from '../../context/AuthContext';

const STARTER_QUERIES = [
  'Food delivery and restaurant purchases',
  'Cloud hosting and server infrastructure',
  'Streaming entertainment subscriptions',
  'Domestic electricity and utility bills',
  'Daily office cab and ride sharing',
  'Salary and payroll credits',
  'Luxury electronics and gadget splurges',
  'Monthly apartment rent payments',
];

export const SemanticSearchView: React.FC = () => {
  const { csrfToken } = useAuth();
  const [query, setQuery] = useState('');
  const [limit, setLimit] = useState(10);
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [searchedQuery, setSearchedQuery] = useState('');
  const [totalResults, setTotalResults] = useState(0);
  const [embeddingModel, setEmbeddingModel] = useState('');
  const [engine, setEngine] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const formatINR = (val: number) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 2,
    }).format(val);
  };

  const handleSearch = async (searchTerm?: string) => {
    const q = (searchTerm ?? query).trim();
    if (!q) return;

    setIsLoading(true);
    setError(null);
    try {
      const resp = await apiClient.ai.search(q, limit, csrfToken);
      setResults(resp.results || []);
      setTotalResults(resp.total_results || 0);
      setEmbeddingModel(resp.embedding_model || 'BAAI/bge-small-en-v1.5');
      setEngine(resp.engine || 'IBM Db2 Native Vector (COSINE) + LangChain DB2VS');
      setSearchedQuery(q);
    } catch (err: any) {
      setError(err?.message || 'Failed to complete semantic vector search on IBM Db2.');
      setResults([]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSearch();
    }
  };

  const onChipClick = (chipQuery: string) => {
    setQuery(chipQuery);
    handleSearch(chipQuery);
  };

  const getRelevanceBadgeStyle = (label?: string, score?: number) => {
    const s = score ?? 0;
    if (s >= 0.80 || label === 'High Match') {
      return 'bg-forest-100/80 text-forest-900 border-forest-300 dark:bg-forest-900/80 dark:text-cream-100 dark:border-forest-700';
    }
    if (s >= 0.65 || label === 'Strong Match') {
      return 'bg-sage-100/80 text-sage-900 border-sage-300 dark:bg-sage-950/70 dark:text-sage-200 dark:border-sage-800';
    }
    if (s >= 0.50 || label === 'Moderate Match') {
      return 'bg-cream-100 text-stone-800 border-gold-300 dark:bg-[#163013] dark:text-gold-300 dark:border-gold-600/50';
    }
    return 'bg-stone-100 text-stone-600 border-stone-300 dark:bg-forest-950/60 dark:text-sage-400 dark:border-forest-800';
  };

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="rounded-2xl border border-stone-200/80 dark:border-forest-900/60 bg-white dark:bg-[#10240d] p-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium bg-forest-50 dark:bg-forest-900/70 text-forest-800 dark:text-sage-300 border border-forest-200 dark:border-forest-800 mb-3">
              <Sparkles className="w-3.5 h-3.5 text-sage-600 dark:text-gold-400" />
              <span>IBM Db2 Native Vector Search & LangChain DB2VS</span>
            </div>
            <h1 className="text-2xl font-bold text-forest-950 dark:text-cream-100 tracking-tight">
              Semantic Transaction Search
            </h1>
            <p className="text-xs sm:text-sm text-stone-500 dark:text-sage-400 mt-1 max-w-2xl">
              Search your financial records by meaning and natural concepts instead of exact keywords.
              Queries are mapped into a 384-dimensional dense semantic space and scored via native Db2 cosine distance.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl border border-stone-200 dark:border-forest-800 bg-stone-50/70 dark:bg-[#163013]/60 text-xs text-stone-600 dark:text-sage-300 font-mono">
              <Database className="w-4 h-4 text-sage-600 dark:text-gold-400" />
              <span>Model: <strong className="text-forest-950 dark:text-cream-100 font-semibold">{embeddingModel || 'BAAI/bge-small-en-v1.5'}</strong></span>
            </div>
          </div>
        </div>

        {/* Search Bar Input */}
        <div className="mt-6 flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-sage-500" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Search concepts: 'food delivery', 'cloud infrastructure', 'monthly streaming'..."
              className="w-full pl-11 pr-4 py-3 bg-white dark:bg-[#0c1a0a] border border-stone-200 dark:border-forest-800 rounded-xl text-forest-950 dark:text-cream-100 placeholder-stone-400 dark:placeholder-sage-500 focus:outline-hidden focus:ring-2 focus:ring-[#15370D] dark:focus:ring-[#E5CD82] transition-all text-xs sm:text-sm shadow-xs"
              disabled={isLoading}
            />
          </div>

          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5 px-3 py-2.5 bg-white dark:bg-[#0c1a0a] border border-stone-200 dark:border-forest-800 rounded-xl text-xs text-stone-600 dark:text-sage-300">
              <SlidersHorizontal className="w-3.5 h-3.5 text-sage-500" />
              <span>Limit:</span>
              <select
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value))}
                className="bg-transparent text-forest-950 dark:text-cream-100 focus:outline-hidden font-medium cursor-pointer"
              >
                <option value={5} className="bg-white dark:bg-[#10240d] text-forest-950 dark:text-cream-100">5</option>
                <option value={10} className="bg-white dark:bg-[#10240d] text-forest-950 dark:text-cream-100">10</option>
                <option value={20} className="bg-white dark:bg-[#10240d] text-forest-950 dark:text-cream-100">20</option>
              </select>
            </div>

            <button
              onClick={() => handleSearch()}
              disabled={isLoading || !query.trim()}
              className="px-5 py-2.5 bg-[#15370D] hover:bg-[#1e4a14] disabled:opacity-50 disabled:cursor-not-allowed text-[#FFF2B4] font-semibold rounded-xl text-xs sm:text-sm transition-all flex items-center justify-center gap-2 shadow-xs border border-forest-800"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Searching...</span>
                </>
              ) : (
                <>
                  <Search className="w-4 h-4" />
                  <span>Search Ledger</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Starter Suggestion Chips */}
        <div className="mt-4 pt-4 border-t border-stone-100 dark:border-forest-900/60">
          <div className="text-xs text-stone-500 dark:text-sage-400 mb-2 flex items-center gap-1.5">
            <Info className="w-3.5 h-3.5 text-sage-500" />
            <span>Try these conceptual searches:</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {STARTER_QUERIES.map((starter) => (
              <button
                key={starter}
                onClick={() => onChipClick(starter)}
                disabled={isLoading}
                className="text-xs px-3 py-1.5 rounded-lg border border-stone-200/90 dark:border-forest-800/80 bg-stone-50/70 dark:bg-[#163013]/60 hover:border-gold-400 dark:hover:border-gold-500 hover:bg-cream-50/60 dark:hover:bg-forest-900/50 text-stone-700 dark:text-cream-100 transition-all flex items-center gap-1.5"
              >
                <span>{starter}</span>
                <ArrowRight className="w-3 h-3 text-sage-400" />
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="rounded-xl border border-rose-200 dark:border-rose-900/60 bg-rose-50/80 dark:bg-rose-950/30 p-4 text-rose-800 dark:text-rose-300 flex items-center gap-3 text-xs">
          <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Loading Skeleton */}
      {isLoading && (
        <div className="rounded-2xl border border-stone-200/80 dark:border-forest-900/60 bg-white dark:bg-[#10240d] p-12 text-center shadow-sm">
          <Loader2 className="w-8 h-8 animate-spin text-sage-600 dark:text-gold-400 mx-auto mb-3" />
          <h3 className="text-sm font-semibold text-forest-950 dark:text-cream-100">Querying IBM Db2 Vector Engine</h3>
          <p className="text-xs text-stone-500 dark:text-sage-400 mt-1 max-w-md mx-auto">
            Computing 384-dimensional query embedding with BAAI/bge-small-en-v1.5 and executing cosine distance ranking against your isolated ledger...
          </p>
        </div>
      )}

      {/* Results Section */}
      {!isLoading && searchedQuery && (
        <div className="space-y-4">
          {/* Metadata Subheader */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 px-1 text-xs text-stone-500 dark:text-sage-400">
            <div>
              <span>Found </span>
              <strong className="text-forest-950 dark:text-cream-100 font-semibold">{totalResults}</strong>
              <span> semantic matches for "</span>
              <span className="text-forest-800 dark:text-gold-400 font-medium">{searchedQuery}</span>
              <span>"</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded bg-stone-100 dark:bg-forest-900 text-stone-700 dark:text-sage-300 font-mono text-[11px] border border-stone-200 dark:border-forest-800">
                {engine || 'IBM Db2 Native Vector (COSINE)'}
              </span>
            </div>
          </div>

          {/* Empty State */}
          {results.length === 0 ? (
            <div className="rounded-2xl border border-stone-200/80 dark:border-forest-900/60 bg-white dark:bg-[#10240d] p-12 text-center shadow-sm">
              <Search className="w-10 h-10 text-stone-400 dark:text-sage-500 mx-auto mb-3" />
              <h3 className="text-sm font-semibold text-forest-950 dark:text-cream-100">No semantic matches found</h3>
              <p className="text-xs text-stone-500 dark:text-sage-400 mt-1 max-w-sm mx-auto">
                No ledger transactions matched the concept "{searchedQuery}". Try broader terms like "groceries", "subscriptions", or "rent".
              </p>
            </div>
          ) : (
            /* Results Cards */
            <div className="space-y-3">
              {results.map((item, idx) => {
                const pctMatch = Math.round(item.similarity_score * 100);
                const isPending = (item.transaction_status || '').toUpperCase() === 'PENDING';

                return (
                  <div
                    key={item.transaction_id || idx}
                    className="group rounded-xl border border-stone-200/80 dark:border-forest-900/60 bg-white dark:bg-[#10240d] hover:border-gold-300 dark:hover:border-forest-700 p-5 transition-all shadow-sm"
                  >
                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                      {/* Left: Merchant, Category, Description */}
                      <div className="space-y-1.5 flex-1">
                        <div className="flex items-center gap-2.5 flex-wrap">
                          <span className="font-semibold text-forest-950 dark:text-cream-100 text-sm sm:text-base tracking-tight">
                            {item.merchant}
                          </span>
                          
                          {/* Category Badge */}
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-[11px] font-medium bg-stone-100 dark:bg-forest-900/60 text-stone-700 dark:text-sage-300 border border-stone-200/60 dark:border-forest-800/60">
                            <Tag className="w-3 h-3 text-sage-500" />
                            {item.category || 'Uncategorized'}
                          </span>

                          {/* Status Badge */}
                          {isPending ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-[#FFF2B4] text-[#15370D] border border-[#E5CD82]">
                              <Clock className="w-3 h-3 text-[#15370D]" />
                              PENDING
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-sage-100/70 dark:bg-sage-950/60 text-sage-800 dark:text-sage-300 border border-sage-200/70 dark:border-sage-800/60">
                              <CheckCircle2 className="w-3 h-3 text-sage-600 dark:text-sage-400" />
                              POSTED
                            </span>
                          )}

                          {/* Relevance Badge */}
                          <span
                            className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-medium border ${getRelevanceBadgeStyle(
                              item.relevance_label,
                              item.similarity_score
                            )}`}
                          >
                            <Sparkles className="w-3 h-3" />
                            <span>{item.relevance_label || 'High Match'} ({pctMatch}% similarity)</span>
                          </span>
                        </div>

                        {/* Description */}
                        {item.description && (
                          <p className="text-xs sm:text-sm text-stone-700 dark:text-stone-300">
                            {item.description}
                          </p>
                        )}

                        {/* Match Explanation */}
                        {item.explanation && (
                          <p className="text-xs text-stone-500 dark:text-sage-400 italic">
                            {item.explanation}
                          </p>
                        )}

                        {/* Audit Details */}
                        <div className="flex items-center gap-4 text-[11px] text-stone-400 dark:text-sage-500 pt-1 font-mono">
                          <span className="flex items-center gap-1">
                            <Calendar className="w-3 h-3" />
                            {item.date}
                          </span>
                          <span>Cosine dist: <strong className="text-stone-700 dark:text-sage-300">{item.distance.toFixed(4)}</strong></span>
                          <span>ID: <strong className="text-stone-700 dark:text-sage-300">{item.transaction_id}</strong></span>
                        </div>
                      </div>

                      {/* Right: Amount & Rationale */}
                      <div className="text-right flex md:flex-col items-center md:items-end justify-between md:justify-center border-t md:border-t-0 pt-3 md:pt-0 border-stone-100 dark:border-forest-900/60">
                        <div className="text-base sm:text-lg font-bold font-mono text-forest-950 dark:text-cream-100 tracking-tight">
                          {formatINR(item.amount)}
                        </div>
                        <div className="text-[11px] font-mono text-sage-600 dark:text-sage-400">
                          {item.currency || 'INR'}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
