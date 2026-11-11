'use client';

import * as React from 'react';
import { AppShell } from '@/components/layout/app-shell';
import { ChatInterface } from '@/components/ai/chat-interface';

export default function AIAssistantPage() {
  return (
    <AppShell title="AI Financial Assistant">
      <div className="space-y-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900">
            SplitSync AI Assistant
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            Autonomous query engine connected to IBM Db2 relational ledgers and settlement models.
          </p>
        </div>

        <ChatInterface />
      </div>
    </AppShell>
  );
}
