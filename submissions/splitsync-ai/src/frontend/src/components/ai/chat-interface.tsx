'use client';

import * as React from 'react';
import { useFetch } from '@/hooks/use-api';
import { MessageBubble, type ChatMessage } from './message-bubble';
import { Select } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';
import { api, ApiError } from '@/lib/api-client';
import type { Group } from '@/lib/types';

export interface ChatInterfaceProps {
  initialGroupId?: string;
}

const QUICK_PROMPTS = [
  'Who owes the most in this group?',
  'What is the total expenditure and contribution summary?',
  'Are there any pending cash approvals?',
  'What are the recommended settlement transfers?',
];

export function ChatInterface({ initialGroupId }: ChatInterfaceProps) {
  const { data: groups } = useFetch<Group[]>('/api/v1/groups');

  const [selectedGroupId, setSelectedGroupId] = React.useState<string>(initialGroupId || '');
  const [messages, setMessages] = React.useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content:
        'Hello! I am your **SplitSync AI Assistant**. Ask me anything about group expenses, member balances, pending cash approvals, or minimum settlement transfers.',
      timestamp: new Date().toISOString(),
    },
  ]);
  const [inputValue, setInputValue] = React.useState<string>('');
  const [isSending, setIsSending] = React.useState<boolean>(false);
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null);

  const messagesEndRef = React.useRef<HTMLDivElement>(null);

  // Set default group when groups load
  React.useEffect(() => {
    if (!selectedGroupId && groups && groups.length > 0) {
      setSelectedGroupId(groups[0].group_id);
    }
  }, [groups, selectedGroupId]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  React.useEffect(() => {
    scrollToBottom();
  }, [messages, isSending]);

  const handleSendMessage = async (textToSend?: string) => {
    const text = (textToSend || inputValue).trim();
    if (!text || isSending) return;

    setErrorMessage(null);
    setInputValue('');

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsSending(true);

    try {
      const response = await api.post<{
        response?: string;
        answer?: string;
        message?: string;
        tools_used?: string[];
      }>('/api/v1/ai/query', {
        prompt: text,
        group_id: selectedGroupId || undefined,
      });

      const assistantReply =
        response?.response ||
        response?.answer ||
        response?.message ||
        'I have analyzed your group ledger records in IBM Db2.';

      const assistantMessage: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: assistantReply,
        tools_used: response?.tools_used || [],
        timestamp: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      if (err instanceof ApiError) {
        setErrorMessage(err.message || 'AI assistant service unavailable.');
      } else if (err instanceof Error) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage('Failed to connect to AI assistant service.');
      }
    } finally {
      setIsSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-12rem)] min-h-[500px] rounded-xl border border-slate-200 bg-slate-50 overflow-hidden shadow-sm">
      {/* Top Banner Notice */}
      <div className="bg-indigo-900 text-indigo-100 px-4 py-2 text-xs flex items-center justify-between border-b border-indigo-950">
        <div className="flex items-center gap-2">
          <span className="flex h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="font-medium">
            All financial figures are queried directly from real IBM Db2 ledger records.
          </span>
        </div>
      </div>

      {/* Group Context Selector Header */}
      <div className="bg-white px-4 py-3 border-b border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-primary-600 text-white flex items-center justify-center font-bold">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
            </svg>
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-900">SplitSync Financial Assistant</h3>
            <p className="text-[11px] text-slate-500">Autonomous analytical queries backed by SQL Db2 tools</p>
          </div>
        </div>

        {groups && groups.length > 0 && (
          <div className="w-full sm:w-64">
            <Select
              value={selectedGroupId}
              onChange={(e) => setSelectedGroupId(e.target.value)}
              options={groups.map((g) => ({
                label: `Group: ${g.name}`,
                value: g.group_id,
              }))}
            />
          </div>
        )}
      </div>

      {/* Messages Thread */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {isSending && (
          <div className="flex items-center gap-3 p-3 rounded-lg bg-white border border-slate-200 text-xs text-slate-600 max-w-sm shadow-sm animate-pulse">
            <Spinner size="sm" />
            <span>SplitSync AI is inspecting Db2 records...</span>
          </div>
        )}

        {errorMessage && (
          <div className="rounded-lg bg-rose-50 border border-rose-200 p-3 text-xs font-medium text-rose-800">
            {errorMessage}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Suggested Prompts Chips */}
      <div className="px-4 py-2 bg-white border-t border-slate-200 overflow-x-auto">
        <div className="flex items-center gap-2 text-xs whitespace-nowrap">
          <span className="text-slate-400 font-medium">Suggestions:</span>
          {QUICK_PROMPTS.map((prompt, i) => (
            <button
              key={i}
              type="button"
              disabled={isSending}
              onClick={() => handleSendMessage(prompt)}
              className="rounded-full bg-slate-100 hover:bg-primary-50 hover:text-primary-700 hover:border-primary-200 border border-slate-200 px-3 py-1 text-slate-700 font-medium transition-colors disabled:opacity-50"
            >
              {prompt}
            </button>
          ))}
        </div>
      </div>

      {/* Chat Input Bar */}
      <div className="p-3 bg-white border-t border-slate-200">
        <div className="flex items-center gap-2">
          <input
            type="text"
            placeholder="Ask about balances, expenses, or settlements..."
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isSending}
            className="flex-1 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-colors disabled:bg-slate-100"
          />
          <Button
            type="button"
            variant="primary"
            size="md"
            disabled={!inputValue.trim() || isSending}
            isLoading={isSending}
            onClick={() => handleSendMessage()}
            className="h-10 px-5 shrink-0"
          >
            <span>Send</span>
          </Button>
        </div>
      </div>
    </div>
  );
}
