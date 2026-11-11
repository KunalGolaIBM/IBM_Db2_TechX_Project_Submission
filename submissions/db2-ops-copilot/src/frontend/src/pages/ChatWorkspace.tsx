import { useRef, useState } from "react";
import { api, ApiClientError } from "../api/client";
import type { ChatMode, ChatResponse, Citation } from "../api/types";
import { EmptyState, ErrorBanner, PageHeader, StatusBadge } from "../components/Ui";
import { errorMessage } from "../hooks/useAsync";

interface Message {
  id: number;
  role: "user" | "assistant";
  text: string;
  response?: ChatResponse;
  error?: string;
}

const MODE_OPTIONS: { value: ChatMode; label: string }[] = [
  { value: "auto", label: "Auto route" },
  { value: "rag", label: "Docs (RAG)" },
  { value: "sql", label: "Data (text-to-SQL)" },
];

let nextId = 1;

export default function ChatWorkspace() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [mode, setMode] = useState<ChatMode>("auto");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  async function send() {
    const text = input.trim();
    if (!text || sending) return;
    setInput("");
    setError(null);
    setMessages((m) => [...m, { id: nextId++, role: "user", text }]);
    setSending(true);
    try {
      const response = await api.chat({ message: text, mode });
      setMessages((m) => [
        ...m,
        { id: nextId++, role: "assistant", text: response.reply, response },
      ]);
    } catch (err) {
      const message =
        err instanceof ApiClientError && err.code === "PROMPT_INJECTION_BLOCKED"
          ? "Message blocked by the prompt-injection defense. Rephrase without instruction-override patterns."
          : errorMessage(err);
      setMessages((m) => [
        ...m,
        { id: nextId++, role: "assistant", text: "", error: message },
      ]);
      setError(message);
    } finally {
      setSending(false);
      requestAnimationFrame(() =>
        listRef.current?.scrollTo({ top: listRef.current.scrollHeight }),
      );
    }
  }

  return (
    <div className="page page-chat">
      <PageHeader
        title="Chat workspace"
        subtitle="Ask about Db2 docs (RAG) or your data (guardrailed text-to-SQL)."
      />

      {error && <ErrorBanner message={error} />}

      <div className="chat-log" ref={listRef}>
        {messages.length === 0 ? (
          <EmptyState
            title="No messages yet"
            hint="Try: “What is DB2VS?” (docs) or “List servers by uptime” (data). Every generated SQL statement passes the validation gate before it is shown."
          />
        ) : (
          messages.map((message) =>
            message.role === "user" ? (
              <div key={message.id} className="msg msg-user">
                <div className="msg-body">{message.text}</div>
              </div>
            ) : message.error ? (
              <div key={message.id} className="msg msg-assistant msg-error">
                <div className="msg-body">{message.error}</div>
              </div>
            ) : (
              <AssistantMessage key={message.id} message={message} />
            ),
          )
        )}
        {sending && (
          <div className="msg msg-assistant">
            <div className="msg-body msg-pending">
              <span className="spinner" aria-hidden /> Thinking…
            </div>
          </div>
        )}
      </div>

      <form
        className="chat-input-bar"
        onSubmit={(event) => {
          event.preventDefault();
          void send();
        }}
      >
        <select
          className="chat-mode"
          value={mode}
          onChange={(event) => setMode(event.target.value as ChatMode)}
          aria-label="Routing mode"
        >
          {MODE_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <input
          className="chat-input"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Ask Db2 Ops Copilot…"
          maxLength={4000}
          disabled={sending}
        />
        <button
          type="submit"
          className="btn btn-primary"
          disabled={sending || input.trim().length === 0}
        >
          {sending ? "…" : "Send"}
        </button>
      </form>
    </div>
  );
}

function AssistantMessage({ message }: { message: Message }) {
  const response = message.response!;
  return (
    <div className="msg msg-assistant">
      <div className="msg-meta">
        <StatusBadge status="neutral" label={`intent: ${response.intent}`} />
        {response.mock && <StatusBadge status="warn" label="mock data" />}
        {response.warnings.map((warning) => (
          <StatusBadge key={warning} status="warn" label={warning} />
        ))}
        <span className="meta-text">{response.timings.total_ms} ms</span>
      </div>
      <div className="msg-body">{response.reply}</div>
      {response.sql && (
        <pre className="msg-sql">
          <code>{response.sql}</code>
        </pre>
      )}
      {response.citations.length > 0 && (
        <div className="citations">
          <div className="citations-title">Sources</div>
          {response.citations.map((citation: Citation, index: number) => (
            <div key={index} className="citation">
              <span className="citation-title">{citation.title}</span>
              <span className="meta-text">{citation.source}</span>
              <p className="citation-snippet">{citation.snippet}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
