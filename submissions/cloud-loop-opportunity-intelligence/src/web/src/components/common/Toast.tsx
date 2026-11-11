"use client";

import React, { createContext, useContext, useState, useCallback, useEffect } from "react";
import { CheckCircle, XCircle, X } from "lucide-react";

type ToastType = "success" | "error" | "info";

interface Toast {
  id: string;
  message: string;
  type: ToastType;
}

interface ToastContextValue {
  showToast: (message: string, type?: ToastType) => void;
  success: (message: string) => void;
  error: (message: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

/** Wrap your app with this provider to enable toasts everywhere */
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const remove = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const showToast = useCallback((message: string, type: ToastType = "info") => {
    const id = `${Date.now()}-${Math.random()}`;
    setToasts((prev) => [...prev.slice(-3), { id, message, type }]);
    setTimeout(() => remove(id), 4500);
  }, [remove]);

  const success = useCallback((msg: string) => showToast(msg, "success"), [showToast]);
  const error = useCallback((msg: string) => showToast(msg, "error"), [showToast]);

  return (
    <ToastContext.Provider value={{ showToast, success, error }}>
      {children}
      {/* Toast container */}
      <div
        aria-live="polite"
        aria-atomic="false"
        className="fixed bottom-5 right-5 z-[9999] flex flex-col gap-2 pointer-events-none"
        style={{ maxWidth: "calc(100vw - 2.5rem)" }}
      >
        {toasts.map((toast) => (
          <ToastItem key={toast.id} toast={toast} onDismiss={() => remove(toast.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: () => void }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    requestAnimationFrame(() => setVisible(true));
  }, []);

  const borderColor = toast.type === "success" ? "#C6F432" : toast.type === "error" ? "#ef4444" : "#C6F432";
  const Icon = toast.type === "success" ? CheckCircle : toast.type === "error" ? XCircle : CheckCircle;
  const iconColor = toast.type === "success" ? "#C6F432" : toast.type === "error" ? "#ef4444" : "#C6F432";

  return (
    <div
      role="alert"
      className="pointer-events-auto flex items-start gap-3 px-4 py-3 rounded-xl text-sm font-medium text-white shadow-2xl"
      style={{
        background: "#0B0B0C",
        border: `1.5px solid ${borderColor}`,
        opacity: visible ? 1 : 0,
        transform: visible ? "translateY(0) scale(1)" : "translateY(12px) scale(0.95)",
        transition: "opacity 0.25s ease, transform 0.25s ease",
        maxWidth: "380px",
      }}
    >
      <Icon size={18} style={{ color: iconColor, flexShrink: 0, marginTop: 1 }} />
      <span className="flex-1 leading-snug">{toast.message}</span>
      <button
        onClick={onDismiss}
        aria-label="Dismiss notification"
        className="shrink-0 text-white/50 hover:text-white transition-colors cursor-pointer"
      >
        <X size={15} />
      </button>
    </div>
  );
}

/** Hook to use toast from any component */
export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside <ToastProvider>");
  return ctx;
}

