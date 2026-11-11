"use client";

import React, { useState, useRef, useEffect } from "react";
import { MessageSquare, X, Send, Sparkles, Bot, User, Database, ExternalLink, Loader2 } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useToast } from "@/components/common/Toast";
import Link from "next/link";

interface Message {
  id: string;
  sender: "user" | "bot";
  text: string;
  sources?: Array<{
    id: string;
    title: string;
    company: string;
    link?: string;
  }>;
  engine?: string;
  timestamp: Date;
}

const SAMPLE_PROMPTS = [
  "What Google student programs are open?",
  "Find remote internships with high stipend",
  "Any beginner-friendly hackathons?",
  "Best cloud certifications for 2026?",
];

export function AiChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      sender: "bot",
      text: "👋 Hi! I'm your AI Opportunity Assistant. Powered by IBM Db2, I can find student programs, internships, fresher jobs, and hackathons matching your goals. Ask me anything!",
      timestamp: new Date(),
    },
  ]);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { showToast } = useToast();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    if (isOpen) {
      scrollToBottom();
    }
  }, [messages, isOpen]);

  const handleSubmit = async (queryText?: string) => {
    const q = (queryText ?? input).trim();
    if (!q || isLoading) return;

    const userMsg: Message = {
      id: `u-${Date.now()}`,
      sender: "user",
      text: q,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsLoading(true);

    try {
      const res = await fetch("/api/db2/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });

      if (!res.ok) {
        throw new Error(`Server returned ${res.status}`);
      }

      const data = await res.json();

      const botMsg: Message = {
        id: `b-${Date.now()}`,
        sender: "bot",
        text: data.answer || "I found relevant opportunities for you.",
        sources: data.sources || [],
        engine: data.engine || "IBM Db2 Hybrid RAG",
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, botMsg]);
    } catch (err) {
      console.error("AI chat error:", err);
      showToast("Could not complete AI search. Try again in a moment.", "error");
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          sender: "bot",
          text: "I encountered an error querying the opportunity index. Please check your network or try a simpler question.",
          timestamp: new Date(),
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed bottom-6 right-6 z-50">
      {/* Floating Toggle Button */}
      <AnimatePresence>
        {!isOpen && (
          <motion.button
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0, opacity: 0 }}
            onClick={() => setIsOpen(true)}
            aria-label="Open AI Opportunity Assistant"
            className="group relative flex items-center justify-center w-14 h-14 rounded-full bg-brand-black border-2 border-brand-lime shadow-lime hover:scale-105 active:scale-95 transition-all cursor-pointer"
          >
            <Sparkles className="w-6 h-6 text-brand-lime group-hover:rotate-12 transition-transform" />
            <span className="absolute -top-1 -right-1 flex h-3.5 w-3.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-brand-lime opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-brand-lime"></span>
            </span>
          </motion.button>
        )}
      </AnimatePresence>

      {/* Chat Window */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            transition={{ duration: 0.2 }}
            className="w-[92vw] sm:w-[420px] h-[580px] max-h-[85vh] flex flex-col rounded-2xl bg-brand-black border border-brand-lime/40 shadow-2xl overflow-hidden text-brand-white"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-brand-lime/20 bg-brand-black/90 backdrop-blur-md">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-brand-lime/10 border border-brand-lime/30 flex items-center justify-center">
                  <Bot className="w-4 h-4 text-brand-lime" />
                </div>
                <div>
                  <div className="flex items-center gap-1.5">
                    <h3 className="text-sm font-bold text-brand-white">Opportunity AI</h3>
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold bg-brand-lime/20 text-brand-lime border border-brand-lime/40">
                      IBM Db2
                    </span>
                  </div>
                  <p className="text-[11px] text-zinc-400">RAG Semantic Search & Q&A</p>
                </div>
              </div>
              <button
                onClick={() => setIsOpen(false)}
                className="p-1.5 rounded-lg text-zinc-400 hover:text-brand-white hover:bg-zinc-800 transition-colors"
                aria-label="Close chat"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Messages Body */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3.5 bg-zinc-950/50">
              {messages.map((m) => (
                <div
                  key={m.id}
                  className={`flex gap-2.5 ${m.sender === "user" ? "justify-end" : "justify-start"}`}
                >
                  {m.sender === "bot" && (
                    <div className="w-7 h-7 rounded-full bg-brand-lime/10 border border-brand-lime/30 flex items-center justify-center shrink-0 mt-0.5">
                      <Bot className="w-3.5 h-3.5 text-brand-lime" />
                    </div>
                  )}

                  <div
                    className={`max-w-[82%] rounded-2xl px-3.5 py-2.5 text-xs leading-relaxed ${
                      m.sender === "user"
                        ? "bg-brand-lime text-brand-black font-medium rounded-br-none"
                        : "bg-zinc-900 border border-zinc-800 text-zinc-200 rounded-bl-none"
                    }`}
                  >
                    <p className="whitespace-pre-wrap">{m.text}</p>

                    {/* Sources (if returned by RAG) */}
                    {m.sources && m.sources.length > 0 && (
                      <div className="mt-2.5 pt-2 border-t border-zinc-800 space-y-1">
                        <div className="text-[10px] uppercase tracking-wider font-semibold text-brand-lime flex items-center gap-1">
                          <Database className="w-3 h-3" />
                          Matched Sources ({m.sources.length}):
                        </div>
                        {m.sources.slice(0, 3).map((src) => (
                          <div
                            key={src.id}
                            className="text-[11px] bg-zinc-950/60 rounded px-2 py-1 flex items-center justify-between text-zinc-300"
                          >
                            <span className="truncate pr-2 font-medium">{src.title} — {src.company}</span>
                            {src.link && (
                              <a
                                href={src.link}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-brand-lime hover:underline shrink-0"
                              >
                                <ExternalLink className="w-3 h-3" />
                              </a>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {m.sender === "user" && (
                    <div className="w-7 h-7 rounded-full bg-zinc-800 flex items-center justify-center shrink-0 mt-0.5 text-zinc-300">
                      <User className="w-3.5 h-3.5" />
                    </div>
                  )}
                </div>
              ))}

              {isLoading && (
                <div className="flex gap-2.5 items-center text-xs text-zinc-400">
                  <div className="w-7 h-7 rounded-full bg-brand-lime/10 border border-brand-lime/30 flex items-center justify-center">
                    <Loader2 className="w-3.5 h-3.5 text-brand-lime animate-spin" />
                  </div>
                  <span>Searching IBM Db2 knowledge base...</span>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Quick Prompts */}
            {messages.length <= 2 && (
              <div className="px-3 py-2 border-t border-zinc-900 bg-zinc-950 flex flex-wrap gap-1.5">
                {SAMPLE_PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    onClick={() => handleSubmit(prompt)}
                    className="text-[10px] px-2.5 py-1 rounded-full bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-brand-lime hover:border-brand-lime/40 transition-colors"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            )}

            {/* Input Bar */}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSubmit();
              }}
              className="p-3 border-t border-brand-lime/20 bg-brand-black flex items-center gap-2"
            >
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask about jobs, programs, hackathons..."
                disabled={isLoading}
                className="flex-1 bg-zinc-900 border border-zinc-800 rounded-xl px-3.5 py-2 text-xs text-brand-white placeholder:text-zinc-500 focus:outline-none focus:border-brand-lime/60"
              />
              <button
                type="submit"
                disabled={isLoading || !input.trim()}
                aria-label="Send message"
                className="p-2 rounded-xl bg-brand-lime text-brand-black hover:bg-brand-lime-dark disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                <Send className="w-4 h-4" />
              </button>
            </form>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

