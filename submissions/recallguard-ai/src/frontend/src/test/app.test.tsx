import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "./utils";

vi.mock("@/services/api", async () => {
  const actual = await vi.importActual<typeof import("@/services/api")>("@/services/api");
  let role = "analyst";
  return {
    ...actual,
    getRole: () => role,
    setRole: (r: string) => { role = r; },
    api: {
      dashboard: vi.fn(), incidents: vi.fn(), catalog: vi.fn(), createIncident: vi.fn(), upload: vi.fn(), investigate: vi.fn(),
      trace: vi.fn(), impact: vi.fn(), approve: vi.fn(), reject: vi.fn(), health: vi.fn(),
    },
  };
});

import { api, setRole } from "@/services/api";
import DashboardPage from "@/pages/DashboardPage";
import { IncidentForm } from "@/pages/IncidentsPage";
import ExplorerPage from "@/pages/ExplorerPage";
import { ApprovalPanel } from "@/pages/RecallDetailPage";

const m = api as unknown as Record<string, ReturnType<typeof vi.fn>>;

const DASH = {
  kpis: { total_incidents: 3, active_incidents: 2, critical_incidents: 1, products_under_investigation: 8, batches_potentially_affected: 11,
          locations_affected: 36, pending_approvals: 2, active_recalls: 1, completed_recalls: 1 },
  risk_distribution: [{ risk_class: "CRITICAL", n: 1 }, { risk_class: "HIGH", n: 1 }],
  status_distribution: [{ incident_status: "PENDING_APPROVAL", n: 2 }],
  timeline: [{ occurred_at: "2026-11-11T10:00:00", actor: "qa", action_name: "INCIDENT_CREATED", entity_kind: "INCIDENT", entity_ref: "INC-2026-ABC", details: "" }],
  network: { suppliers: 12, lots: 27, batches: 33, products: 17, warehouses: 10, distributors: 6, retailers: 30, shipments: 192 },
  shipments_by_destination: [], engine: "IBM Db2",
};

beforeEach(() => { Object.values(m).forEach((f) => f.mockReset()); setRole("analyst"); });

describe("Executive dashboard", () => {
  it("renders KPIs, risk distribution and incidents", async () => {
    m.dashboard.mockResolvedValue(DASH);
    m.incidents.mockResolvedValue([{ incident_id: "INC-2026-ABC", title: "Salmonella in tomato puree", source_ref: "TOM-2026-041", severity: "CRITICAL",
      incident_status: "PENDING_APPROVAL", discovered_at: "2026-11-11T09:00:00" }]);
    renderWithProviders(<DashboardPage />);
    const kpis = await screen.findByTestId("kpis");
    expect(within(kpis).getByText("Potentially affected batches")).toBeInTheDocument();
    expect(within(kpis).getByText("11")).toBeInTheDocument();
    expect(within(kpis).getByText("36")).toBeInTheDocument();
    expect(await screen.findByText("Salmonella in tomato puree")).toBeInTheDocument();
    expect(screen.getAllByText("CRITICAL").length).toBeGreaterThan(0);
  });

  it("shows a loading state, then an error state with retry", async () => {
    let reject!: (e: Error) => void;
    m.dashboard.mockReturnValue(new Promise((_, r) => { reject = r; }));
    m.incidents.mockResolvedValue([]);
    renderWithProviders(<DashboardPage />);
    expect(screen.getByLabelText("Loading dashboard")).toBeInTheDocument();
    reject(new Error("Cannot reach the RecallGuard API"));
    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the RecallGuard API");
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});

describe("Incident creation", () => {
  it("creates an incident, uploads the lab report and starts the investigation", async () => {
    m.catalog.mockResolvedValue({ lots: [{ lot_id: "TOM-2026-041", ingredient_name: "Tomato puree", supplier_name: "Valle Rosso" }], batches: [], suppliers: [] });
    m.createIncident.mockResolvedValue({ incident_id: "INC-2026-NEW" });
    m.upload.mockResolvedValue({ document_id: "DOC-1" });
    m.investigate.mockResolvedValue({ run_id: "RUN-1" });
    const user = userEvent.setup();
    renderWithProviders(<IncidentForm />);
    await user.type(screen.getByPlaceholderText(/Salmonella in tomato/i), "Salmonella in tomato puree lot");
    await user.type(screen.getByPlaceholderText("TOM-2026-041"), "TOM-2026-041");
    await user.type(screen.getByPlaceholderText("Salmonella Typhimurium"), "Salmonella Typhimurium");
    await user.selectOptions(screen.getByLabelText("Severity"), "CRITICAL");
    const file = new File(["%PDF-1.4 lab"], "lab.pdf", { type: "application/pdf" });
    await user.upload(screen.getByLabelText("Laboratory report"), file);
    await user.click(screen.getByRole("button", { name: /Register incident/i }));
    await waitFor(() => expect(m.createIncident).toHaveBeenCalled());
    expect(m.createIncident.mock.calls[0][0]).toMatchObject({ source_ref: "TOM-2026-041", severity: "CRITICAL", contamination_category: "MICROBIAL" });
    await waitFor(() => expect(m.upload).toHaveBeenCalledWith(file, "lab.pdf", "INC-2026-NEW"));
    expect(m.investigate).toHaveBeenCalledWith("INC-2026-NEW");
    expect(await screen.findByText("investigation page")).toBeInTheDocument();
  });

  it("shows server validation errors", async () => {
    m.catalog.mockResolvedValue({ lots: [], batches: [], suppliers: [] });
    m.createIncident.mockRejectedValue(new Error("No ingredient lot or production batch with id 'NOP-2026-999'"));
    const user = userEvent.setup();
    renderWithProviders(<IncidentForm />);
    await user.type(screen.getByPlaceholderText(/Salmonella in tomato/i), "Unknown lot test");
    await user.type(screen.getByPlaceholderText("TOM-2026-041"), "NOP-2026-999");
    await user.type(screen.getByPlaceholderText("Salmonella Typhimurium"), "Salmonella");
    await user.click(screen.getByRole("button", { name: /Register incident/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("NOP-2026-999");
  });
});

describe("Batch tracing", () => {
  it("renders the Db2 genealogy graph and executed queries", async () => {
    m.catalog.mockResolvedValue({ lots: [], batches: [], suppliers: [] });
    m.trace.mockResolvedValue({
      root: { kind: "BATCH", ref: "PB-2026-1007" }, engine: "IBM Db2",
      nodes: [
        { id: "TOM-2026-041", type: "lot", label: "TOM-2026-041", layer: 1, affected: true },
        { id: "PB-2026-1007", type: "finished", label: "PB-2026-1007", layer: 4, affected: true, focus: true },
        { id: "RTL-DEL-01", type: "retailer", label: "Capital Fresh Saket", layer: 6, affected: true },
      ],
      edges: [{ id: "a", source: "TOM-2026-041", target: "PB-2026-1007", kind: "transform", label: "400 KG" }],
      queries: [{ query: "upstream_genealogy", rows: 7, ms: 1.2, params: [] }],
    });
    m.impact.mockResolvedValue(null);
    renderWithProviders(<ExplorerPage />, { route: "/explorer?ref=PB-2026-1007" });
    expect(await screen.findByTestId("supply-graph")).toBeInTheDocument();
    expect(await screen.findByText("upstream_genealogy")).toBeInTheDocument();
    expect(m.trace).toHaveBeenCalledWith("PB-2026-1007");
    expect(screen.getByText(/3 affected by open incidents/)).toBeInTheDocument();
  });

  it("shows an error when the batch does not exist", async () => {
    m.catalog.mockResolvedValue({ lots: [], batches: [], suppliers: [] });
    m.trace.mockRejectedValue(new Error("No ingredient lot or production batch with id 'PB-0000'"));
    m.impact.mockRejectedValue(new Error("x"));
    renderWithProviders(<ExplorerPage />, { route: "/explorer?ref=PB-0000" });
    expect(await screen.findByText(/No ingredient lot or production batch/)).toBeInTheDocument();
  });
});

describe("Recall approval", () => {
  it("lets a recall manager approve", async () => {
    setRole("recall_manager");
    m.approve.mockResolvedValue({ recall_id: "RC-1", recall_status: "EXECUTING" });
    const user = userEvent.setup();
    renderWithProviders(<ApprovalPanel recallId="RC-1" status="PENDING_APPROVAL" />);
    await user.click(screen.getByRole("button", { name: /Approve/ }));
    await waitFor(() => expect(m.approve).toHaveBeenCalledWith("RC-1", expect.stringContaining("Approved")));
  });

  it("requires a comment to reject and blocks analysts", async () => {
    setRole("recall_manager");
    const user = userEvent.setup();
    const { unmount } = renderWithProviders(<ApprovalPanel recallId="RC-1" status="PENDING_APPROVAL" />);
    expect(screen.getByRole("button", { name: /Reject/ })).toBeDisabled();
    await user.type(screen.getByLabelText("Decision comment"), "Insufficient evidence");
    m.reject.mockResolvedValue({ recall_id: "RC-1", recall_status: "REJECTED" });
    await user.click(screen.getByRole("button", { name: /Reject/ }));
    await waitFor(() => expect(m.reject).toHaveBeenCalledWith("RC-1", "Insufficient evidence"));
    unmount();
    setRole("analyst");
    renderWithProviders(<ApprovalPanel recallId="RC-1" status="PENDING_APPROVAL" />);
    expect(screen.getByRole("button", { name: /Approve/ })).toBeDisabled();
    expect(screen.getByText(/cannot approve or reject/)).toBeInTheDocument();
  });

  it("renders nothing once decided", () => {
    const { container } = renderWithProviders(<ApprovalPanel recallId="RC-1" status="EXECUTING" />);
    expect(container).toBeEmptyDOMElement();
  });
});
