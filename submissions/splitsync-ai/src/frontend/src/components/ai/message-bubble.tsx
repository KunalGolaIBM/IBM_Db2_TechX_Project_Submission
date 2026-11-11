'use client';

import * as React from 'react';
import { Badge } from '@/components/ui/badge';
import { formatDateTime } from '@/lib/utils';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  tools_used?: string[];
  timestamp: string;
}

export interface MessageBubbleProps {
  message: ChatMessage;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user';

  // Simple markdown renderer for bold, code, lists, and linebreaks
  const renderFormattedContent = (text: string) => {
    const lines = text.split('\n');

    return lines.map((line, idx) => {
      // Unordered List Item
      if (line.startsWith('- ') || line.startsWith('* ')) {
        const itemText = line.substring(2);
        return (
          <li key={idx} className="ml-4 list-disc text-sm leading-relaxed my-0.5">
            {formatInlineTokens(itemText)}
          </li>
        );
      }

      // Ordered list Item
      const matchNumbered = line.match(/^(\d+)\.\s+(.*)$/);
      if (matchNumbered) {
        return (
          <li key={idx} className="ml-4 list-decimal text-sm leading-relaxed my-0.5">
            {formatInlineTokens(matchNumbered[2])}
          </li>
        );
      }

      // Empty line / paragraph gap
      if (!line.trim()) {
        return <div key={idx} className="h-2" />;
      }

      // Standard text line
      return (
        <p key={idx} className="text-sm leading-relaxed my-1">
          {formatInlineTokens(line)}
        </p>
      );
    });
  };

  const formatInlineTokens = (text: string) => {
    // Process **bold** and `code`
    const parts = text.split(/(\*\*.*?\*\*|`.*?`)/g);

    return parts.map((part, index) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return (
          <strong key={index} className="font-semibold text-slate-900">
            {part.slice(2, -2)}
          </strong>
        );
      }
      if (part.startsWith('`') && part.endsWith('`')) {
        return (
          <code
            key={index}
            className="rounded bg-slate-100 px-1 py-0.5 font-mono text-xs text-indigo-700 border border-slate-200"
          >
            {part.slice(1, -1)}
          </code>
        );
      }
      return part;
    });
  };

  return (
    <div className={`flex w-full ${isUser ? 'justify-end' : 'justify-start'} my-3`}>
      <div
        className={`max-w-[85%] sm:max-w-[75%] rounded-2xl px-4 py-3 shadow-sm ${
          isUser
            ? 'bg-primary-600 text-white rounded-br-none'
            : 'bg-white text-slate-800 border border-slate-200 rounded-bl-none'
        }`}
      >
        {/* Header / Role indicator */}
        <div className="flex items-center justify-between gap-3 mb-1.5">
          <span
            className={`text-[11px] font-bold uppercase tracking-wider ${
              isUser ? 'text-primary-100' : 'text-primary-700'
            }`}
          >
            {isUser ? 'You' : 'SplitSync Assistant'}
          </span>
          <span
            className={`text-[10px] ${
              isUser ? 'text-primary-200' : 'text-slate-400'
            }`}
          >
            {formatDateTime(message.timestamp)}
          </span>
        </div>

        {/* Content */}
        <div className={`space-y-1 ${isUser ? 'text-white' : 'text-slate-800'}`}>
          {renderFormattedContent(message.content)}
        </div>

        {/* Tools Used Badges */}
        {!isUser && message.tools_used && message.tools_used.length > 0 && (
          <div className="mt-3 pt-2 border-t border-slate-100 flex items-center gap-1.5 flex-wrap">
            <span className="text-[10px] uppercase font-bold text-slate-400">
              Db2 Tools:
            </span>
            {message.tools_used.map((tool, i) => (
              <Badge
                key={i}
                variant="info"
                className="text-[10px] font-mono px-1.5 py-0 bg-indigo-50 text-indigo-700 border-indigo-200"
              >
                {tool}
              </Badge>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
