// @vitest-environment jsdom
import { describe, expect, it, vi, beforeEach } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock("../api", async (orig) => ({ ...(await orig<typeof import("../api")>()), api: { get, post, delete: vi.fn(), interceptors: { request: { use: vi.fn() } } } }));
import App from "../App";
import Reports from "../pages/Reports";
import Agents from "../pages/Agents";

beforeEach(() => { cleanup(); sessionStorage.clear(); get.mockReset(); post.mockReset(); });

describe("UI smoke", () => {
  it("shows sign in when logged out", () => {
    render(<MemoryRouter><App /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: "Sign in" })).toBeTruthy();
  });
  it("shows the server's error on a failed login (no fake success)", async () => {
    post.mockRejectedValue({ response: { data: { detail: "Invalid credentials" } } });
    render(<MemoryRouter><App /></MemoryRouter>);
    const { fireEvent } = await import("@testing-library/react");
    fireEvent.change(screen.getByLabelText(/Username/), { target: { value: "alice" } });
    fireEvent.change(screen.getByLabelText(/Password/), { target: { value: "wrongpass1" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Sign in" })[0]);
    await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("Invalid credentials"));
  });
  it("reports page shows an honest empty state", async () => {
    get.mockResolvedValue({ data: [] });
    render(<Reports />);
    await waitFor(() => expect(screen.getByText(/No reports yet/)).toBeTruthy());
  });
  it("agents page lists runs from the API and explains the empty activity panel", async () => {
    get.mockImplementation((url: string) => Promise.resolve({ data: url.includes("runs") ? [{ run_id: 7, status: "COMPLETED", mode: "DETERMINISTIC" }] : [] }));
    render(<MemoryRouter><Agents /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText(/Run #7/)).toBeTruthy());
    expect(screen.getByText(/Select or start a run/)).toBeTruthy();
  });
});
