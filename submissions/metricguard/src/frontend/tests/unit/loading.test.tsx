import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LoadingState } from "@/components/analytics/LoadingState";
import { ANALYZE_TIMEOUT_MS } from "@/lib/api/client";

describe("LoadingState", () => {
  it("shows no slow hint in the first seconds", () => {
    render(<LoadingState question="q" elapsedMs={1500} llm />);
    expect(screen.queryByTestId("slow-hint")).not.toBeInTheDocument();
  });

  it("names the AI planner as the slow step in LLM mode", () => {
    render(<LoadingState question="q" elapsedMs={8000} llm />);
    expect(screen.getByTestId("slow-hint")).toHaveTextContent("Still working · 8 s. The AI planner is usually the slow step.");
  });

  it("does not mention an AI planner in demo mode", () => {
    render(<LoadingState question="q" elapsedMs={8000} />);
    expect(screen.getByTestId("slow-hint")).not.toHaveTextContent(/AI planner/);
  });

  it("after 30 s says when the request will stop and that it can be cancelled", () => {
    render(<LoadingState question="q" elapsedMs={42_000} llm />);
    expect(screen.getByTestId("slow-hint")).toHaveTextContent(`stops by itself after ${ANALYZE_TIMEOUT_MS / 1000} s, or cancel and retry`);
  });
});
