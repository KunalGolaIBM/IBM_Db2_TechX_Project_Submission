"use client";

import { useEffect } from "react";
import { RefreshCw, Home } from "lucide-react";
import Link from "next/link";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[GlobalError]", error);
  }, [error]);

  return (
    <html lang="en">
      <body style={{ background: "#0B0B0C", color: "#FFFFFF", fontFamily: "system-ui, sans-serif", display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh", padding: "2rem" }}>
        <div style={{ textAlign: "center", maxWidth: "480px" }}>
          <div style={{ fontSize: "4rem", marginBottom: "1rem" }}>⚡</div>
          <h1 style={{ fontSize: "1.75rem", fontWeight: 800, marginBottom: "0.75rem", color: "#C6F432" }}>
            Something went wrong
          </h1>
          <p style={{ color: "#A0A09A", marginBottom: "2rem", lineHeight: 1.6 }}>
            An unexpected error occurred. It&apos;s been noted — please try again.
          </p>
          <div style={{ display: "flex", gap: "0.75rem", justifyContent: "center", flexWrap: "wrap" }}>
            <button
              onClick={reset}
              style={{ display: "inline-flex", alignItems: "center", gap: "0.5rem", padding: "0.75rem 1.5rem", borderRadius: "9999px", background: "linear-gradient(135deg, #C6F432, #A8D620)", color: "#0B0B0C", fontWeight: 700, border: "none", cursor: "pointer", fontSize: "0.9rem" }}
            >
              <RefreshCw size={16} /> Try Again
            </button>
            <a
              href="/"
              style={{ display: "inline-flex", alignItems: "center", gap: "0.5rem", padding: "0.75rem 1.5rem", borderRadius: "9999px", border: "1.5px solid rgba(198,244,50,0.4)", color: "#C6F432", fontWeight: 600, textDecoration: "none", fontSize: "0.9rem" }}
            >
              <Home size={16} /> Go Home
            </a>
          </div>
        </div>
      </body>
    </html>
  );
}

