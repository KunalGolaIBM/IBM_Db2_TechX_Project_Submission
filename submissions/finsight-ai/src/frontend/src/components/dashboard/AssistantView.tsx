import React, { useState, useEffect, useRef } from 'react';
import { 
  Bot, 
  User as UserIcon, 
  Send, 
  Loader2, 
  Sparkles, 
  Database, 
  ShieldCheck, 
  ChevronDown, 
  ChevronUp, 
  Trash2, 
  AlertCircle,
  ArrowRight
} from 'lucide-react';
import { apiClient, ChatResponse, EvidenceItem, AiStatusResponse } from '../../api/client';
import { useAuth } from '../../context/AuthContext';

export interface MessageItem {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  evidence?: EvidenceItem[];
  modelUsed?: string;
  intentDetected?: string;
  isGrounded?: boolean;
}

interface AssistantViewProps {
  messages: MessageItem[];
  setMessages: React.Dispatch<React.SetStateAction<MessageItem[]>>;
}

const STARTER_QUESTIONS = [
  {
    title: 'Dining Spend in September',
    question: 'How much did I spend on dining in September?',
    category: 'Category Drilldown'
  },
  {
    title: 'Biggest Expenses',
    question: 'What were my biggest expenses last month?',
    category: 'Outflow Analysis'
  },
  {
    title: '3-Month Cash Flow',
    question: 'Compare my income and expenses over the last three months.',
    category: 'Trend Comparison'
  },
  {
    title: 'Top Merchants',
    question: 'Which merchants received the most money?',
    category: 'Vendor Ranking'
  },
  {
    title: 'Active Subscriptions',
    question: 'Show my recent subscriptions.',
    category: 'Recurring Charges'
  },
  {
    title: 'Pending Transactions',
    question: 'Show my recent pending transactions.',
    category: 'Ledger Settlement'
  },
  {
    title: 'Monthly Savings',
    question: 'How much money did I save this month?',
    category: 'Net Surplus'
  },
];

export const AssistantView: React.FC<AssistantViewProps> = ({ messages, setMessages }) => {
  const { csrfToken } = useAuth();
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [aiStatus, setAiStatus] = useState<AiStatusResponse | null>(null);
  const [expandedEvidence, setExpandedEvidence] = useState<Record<string, boolean>>({});
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to latest message
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  // Fetch AI status on mount
  useEffect(() => {
    let isMounted = true;
    apiClient.ai.getStatus()
      .then((status) => {
        if (isMounted) setAiStatus(status);
      })
      .catch((err) => {
        console.warn('Could not fetch AI status:', err);
      });
    return () => {
      isMounted = false;
    };
  }, []);

  const handleSendMessage = async (textToSend?: string) => {
    const text = (textToSend || inputValue).trim();
    if (!text || isLoading) return;

    setError(null);
    const userMsgId = `user_${Date.now()}`;
    const newUserMsg: MessageItem = {
      id: userMsgId,
      role: 'user',
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, newUserMsg]);
    setInputValue('');
    setIsLoading(true);

    try {
      const res: ChatResponse = await apiClient.ai.chat(text, 'auto', csrfToken);
      const assistantMsgId = `asst_${Date.now()}`;
      const newAssistantMsg: MessageItem = {
        id: assistantMsgId,
        role: 'assistant',
        content: res.answer,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        evidence: res.evidence,
        modelUsed: res.model_used,
        intentDetected: res.intent_detected,
        isGrounded: res.is_grounded,
      };

      setMessages((prev) => [...prev, newAssistantMsg]);
      // Expand evidence by default if available
      if (res.evidence && res.evidence.length > 0) {
        setExpandedEvidence((prev) => ({ ...prev, [assistantMsgId]: true }));
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to process financial intelligence query. Please try again.');
    } finally {
      setIsLoading(false);
      setTimeout(() => textareaRef.current?.focus(), 100);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const clearConversation = () => {
    setMessages([]);
    setError(null);
  };

  const toggleEvidence = (msgId: string) => {
    setExpandedEvidence((prev) => ({
      ...prev,
      [msgId]: !prev[msgId],
    }));
  };

  return (
    <div className="space-y-6">
      {/* Header & Telemetry Status Card */}
      <div className="p-6 rounded-2xl border border-stone-200/80 dark:border-forest-900/60 bg-white dark:bg-[#10240d] shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center space-x-2">
              <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-cream-100 dark:bg-forest-900/70 text-forest-950 dark:text-cream-100 border border-gold-300/70 dark:border-forest-700/70">
                <Sparkles className="w-2.5 h-2.5 mr-0.5 text-sage-600 dark:text-gold-400" />
                Conversational Financial Intelligence
              </span>
              <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-forest-50 dark:bg-forest-950/70 text-forest-800 dark:text-sage-300 border border-forest-200 dark:border-forest-800">
                <Database className="w-2.5 h-2.5 text-sage-600 dark:text-sage-400" />
                <span>Db2 Grounded</span>
              </span>
            </div>
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-forest-950 dark:text-cream-100">
              Financial AI Assistant
            </h1>
            <p className="text-xs text-stone-500 dark:text-sage-400 max-w-2xl">
              Answers and insights are synthesized directly from your verified IBM Db2 ledger records. Numerical assertions are mathematically computed and strictly tenant-isolated.
            </p>
          </div>

          {/* Engine Status Badge */}
          <div className="flex flex-wrap items-center gap-2 self-start md:self-auto text-xs">
            <div className="p-2.5 rounded-xl border border-stone-200 dark:border-forest-800 bg-stone-50/70 dark:bg-[#163013]/60 text-[11px] space-y-1">
              <div className="flex items-center space-x-1.5 text-forest-950 dark:text-cream-100 font-medium">
                <ShieldCheck className="w-3.5 h-3.5 text-sage-600 dark:text-gold-400" />
                <span>{aiStatus?.engine_name || 'Mode A: Deterministic Db2 SQL Engine'}</span>
              </div>
              <div className="text-[10px] text-stone-500 dark:text-sage-400 font-mono flex items-center space-x-2">
                <span>Vector: 384-dim BAAI/bge-small</span>
                <span>·</span>
                <span className={aiStatus?.llm_configured ? 'text-forest-700 dark:text-gold-400 font-semibold' : 'text-stone-600 dark:text-sage-300'}>
                  {aiStatus?.llm_configured ? 'LLM: Gemini Active' : 'LLM: Mode A (Zero Hallucination)'}
                </span>
              </div>
            </div>

            {messages.length > 0 && (
              <button
                onClick={clearConversation}
                className="p-2 rounded-xl border border-stone-200 dark:border-forest-800 text-stone-500 hover:text-rose-600 dark:hover:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/30 transition-colors"
                title="Clear conversation"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Main Conversation Canvas */}
      <div className="rounded-2xl border border-stone-200/80 dark:border-forest-900/60 bg-white dark:bg-[#10240d] shadow-sm overflow-hidden flex flex-col h-[580px]">
        {/* Messages Scroll Area */}
        <div className="flex-1 p-4 sm:p-6 overflow-y-auto space-y-6">
          {messages.length === 0 ? (
            /* Starter Prompts Empty State */
            <div className="h-full flex flex-col justify-center items-center text-center max-w-xl mx-auto space-y-6 py-6">
              <div className="w-12 h-12 rounded-2xl bg-[#15370D] text-[#FFF2B4] flex items-center justify-center shadow-sm border border-forest-800">
                <Bot className="w-6 h-6" />
              </div>
              <div className="space-y-1.5">
                <h3 className="text-base font-bold text-forest-950 dark:text-cream-100">
                  Ask anything about your money
                </h3>
                <p className="text-xs text-stone-500 dark:text-sage-400 leading-relaxed">
                  Every query is mapped to parameterized IBM Db2 aggregations and vector searches. Select a verified prompt or type your question below.
                </p>
              </div>

              {/* Starter Questions Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full text-left pt-2">
                {STARTER_QUESTIONS.map((q, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSendMessage(q.question)}
                    className="p-3 rounded-xl border border-stone-200/90 dark:border-forest-800/80 bg-stone-50/60 dark:bg-forest-900/30 hover:border-gold-400 dark:hover:border-gold-500 hover:bg-cream-50/50 dark:hover:bg-forest-900/60 transition-all text-xs group"
                  >
                    <div className="text-[10px] font-mono text-sage-600 dark:text-gold-400 font-semibold mb-1">
                      {q.category}
                    </div>
                    <div className="font-medium text-stone-800 dark:text-cream-100 group-hover:text-forest-950 dark:group-hover:text-white flex items-center justify-between">
                      <span className="truncate">{q.question}</span>
                      <ArrowRight className="w-3 h-3 text-sage-400 opacity-0 group-hover:opacity-100 transition-opacity ml-1 shrink-0" />
                    </div>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            /* Message Thread */
            <>
              {messages.map((msg) => {
                const isUser = msg.role === 'user';
                const hasEvidence = msg.evidence && msg.evidence.length > 0;
                const isEvExpanded = expandedEvidence[msg.id];

                return (
                  <div
                    key={msg.id}
                    className={`flex items-start space-x-3 ${isUser ? 'flex-row-reverse space-x-reverse' : ''}`}
                  >
                    {/* Avatar */}
                    <div
                      className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 border ${
                        isUser
                          ? 'bg-[#15370D] text-[#FFF2B4] border-forest-800 shadow-xs'
                          : 'bg-sage-600 text-white dark:bg-forest-800 dark:text-gold-300 border-sage-700 dark:border-forest-700 shadow-xs'
                      }`}
                    >
                      {isUser ? <UserIcon className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                    </div>

                    {/* Bubble */}
                    <div className={`space-y-2 max-w-[85%] sm:max-w-[78%] ${isUser ? 'text-right' : 'text-left'}`}>
                      <div
                        className={`inline-block p-4 rounded-2xl text-xs leading-relaxed ${
                          isUser
                            ? 'bg-[#15370D] text-[#FAF8F3] dark:bg-[#183d10] dark:text-cream-100 rounded-tr-xs shadow-xs border border-forest-800'
                            : 'bg-stone-50 dark:bg-[#163013]/90 text-stone-900 dark:text-cream-100 border border-stone-200/80 dark:border-forest-800/80 rounded-tl-xs shadow-xs'
                        }`}
                      >
                        {/* Text Content with Markdown-style bold & tables */}
                        <div className="whitespace-pre-wrap font-sans">
                          {msg.content}
                        </div>
                      </div>

                      {/* Assistant Evidence Attachment */}
                      {!isUser && hasEvidence && (
                        <div className="rounded-xl border border-stone-200 dark:border-forest-800/80 bg-stone-50 dark:bg-[#12280f]/80 overflow-hidden text-left text-xs">
                          <button
                            onClick={() => toggleEvidence(msg.id)}
                            className="w-full px-3.5 py-2 flex items-center justify-between font-mono text-[11px] text-stone-600 dark:text-sage-300 hover:bg-stone-100 dark:hover:bg-forest-900/50 transition-colors"
                          >
                            <span className="flex items-center space-x-1.5 font-semibold">
                              <ShieldCheck className="w-3.5 h-3.5 text-sage-600 dark:text-gold-400" />
                              <span>Db2 Grounding Evidence ({msg.evidence?.length} item{msg.evidence && msg.evidence.length > 1 ? 's' : ''})</span>
                            </span>
                            {isEvExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                          </button>

                          {isEvExpanded && (
                            <div className="p-3.5 border-t border-stone-200 dark:border-forest-800/80 space-y-3 font-mono text-[11px]">
                              {msg.evidence?.map((ev, eIdx) => (
                                <div key={eIdx} className="space-y-1.5 bg-white dark:bg-[#0f200c] p-3 rounded-lg border border-stone-200/70 dark:border-forest-800/60">
                                  <div className="flex items-center justify-between text-stone-500 dark:text-sage-400">
                                    <span className="font-bold text-forest-800 dark:text-gold-400">{ev.evidence_type}</span>
                                    {ev.transaction_ids && ev.transaction_ids.length > 0 && (
                                      <span className="text-[10px] text-stone-400 dark:text-sage-500">{ev.transaction_ids.length} tx IDs linked</span>
                                    )}
                                  </div>

                                  {ev.source_query && (
                                    <div className="p-2 rounded bg-stone-50 dark:bg-[#142d0f] text-[10px] text-stone-700 dark:text-sage-200 break-all border border-stone-200/60 dark:border-forest-800">
                                      <code>{ev.source_query}</code>
                                    </div>
                                  )}

                                  {ev.notes && (
                                    <div className="text-[10px] text-stone-500 dark:text-sage-400 italic">
                                      {ev.notes}
                                    </div>
                                  )}
                                </div>
                              ))}

                              {msg.modelUsed && (
                                <div className="text-[10px] text-stone-400 dark:text-sage-400 flex items-center justify-between pt-1 border-t border-stone-100 dark:border-forest-800/60">
                                  <span>Engine: {msg.modelUsed}</span>
                                  <span>Intent: {msg.intentDetected}</span>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      )}

                      {/* Timestamp */}
                      <div className="text-[10px] text-stone-400 dark:text-sage-500 font-mono px-1">
                        {msg.timestamp}
                      </div>
                    </div>
                  </div>
                );
              })}

              {/* In-Flight Loading Indicator */}
              {isLoading && (
                <div className="flex items-start space-x-3">
                  <div className="w-8 h-8 rounded-xl bg-sage-600 text-white flex items-center justify-center shrink-0 shadow-xs">
                    <Bot className="w-4 h-4" />
                  </div>
                  <div className="p-4 rounded-2xl rounded-tl-xs bg-stone-50 dark:bg-[#163013]/90 border border-stone-200/80 dark:border-forest-800/80 text-xs flex items-center space-x-2.5 text-stone-600 dark:text-sage-300">
                    <Loader2 className="w-4 h-4 animate-spin text-sage-600 dark:text-gold-400" />
                    <span>Analyzing IBM Db2 financial records...</span>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        {/* Error Alert Bar */}
        {error && (
          <div className="px-4 py-2.5 bg-rose-50 dark:bg-rose-950/50 border-t border-rose-200 dark:border-rose-800 text-rose-700 dark:text-rose-300 text-xs flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <AlertCircle className="w-4 h-4 text-rose-500 shrink-0" />
              <span>{error}</span>
            </div>
            <button
              onClick={() => handleSendMessage()}
              className="px-2 py-0.5 rounded bg-rose-200 dark:bg-rose-900 text-rose-900 dark:text-rose-100 text-[10px] font-semibold hover:bg-rose-300"
            >
              Retry
            </button>
          </div>
        )}

        {/* Input & Control Box */}
        <div className="p-3 sm:p-4 border-t border-stone-100 dark:border-forest-900/60 bg-stone-50/70 dark:bg-[#0c1a0a]/60">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendMessage();
            }}
            className="flex items-end space-x-2"
          >
            <div className="relative flex-1">
              <textarea
                ref={textareaRef}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask about expenses, income, subscriptions, merchants, or savings..."
                rows={1}
                disabled={isLoading}
                className="w-full resize-none p-3 pr-10 text-xs rounded-xl border border-stone-200 dark:border-forest-800 bg-white dark:bg-[#10240d] text-forest-950 dark:text-cream-100 placeholder-stone-400 dark:placeholder-sage-500 focus:outline-hidden focus:ring-2 focus:ring-[#15370D] dark:focus:ring-[#E5CD82] transition-all shadow-xs max-h-32 disabled:opacity-60"
              />
            </div>

            <button
              type="submit"
              disabled={!inputValue.trim() || isLoading}
              className="p-3 rounded-xl bg-[#15370D] text-[#FFF2B4] dark:bg-[#E5CD82] dark:text-[#15370D] font-semibold disabled:opacity-40 hover:scale-[1.02] active:scale-[0.98] transition-all shadow-xs flex items-center justify-center shrink-0 border border-forest-800 dark:border-gold-300"
              title="Send message (Enter)"
            >
              {isLoading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </button>
          </form>

          <div className="mt-2 flex items-center justify-between text-[10px] text-stone-400 dark:text-sage-400 px-1">
            <span>Press <kbd className="px-1 py-0.5 rounded bg-stone-200 dark:bg-forest-900 font-mono text-stone-700 dark:text-sage-300">Enter</kbd> to send, <kbd className="px-1 py-0.5 rounded bg-stone-200 dark:bg-forest-900 font-mono text-stone-700 dark:text-sage-300">Shift + Enter</kbd> for newline</span>
            <span>All responses grounded on live Db2 tables</span>
          </div>
        </div>
      </div>
    </div>
  );
};
