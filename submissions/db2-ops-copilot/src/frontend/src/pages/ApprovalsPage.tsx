import { useState, type FormEvent } from "react";
import { api } from "../api/client";
import type { Approval, ApprovalExecutionMode, ApprovalListResponse } from "../api/types";
import { EmptyState, ErrorBanner, PageHeader, Spinner, StatusBadge } from "../components/Ui";
import { errorMessage, useAsync } from "../hooks/useAsync";

function modeMessage(mode: ApprovalExecutionMode): string {
  switch (mode) {
    case "mock_simulated":
      return "Mock mode: approvals are simulated only. No Db2 connection or SQL execution occurs.";
    case "disabled":
      return "Admin execution is disabled. Decisions are recorded, but approved actions will not execute.";
    case "admin_not_configured":
      return "Admin credentials are not configured. Decisions are recorded, but approved actions will not execute.";
    case "enabled_unverified":
      return "Admin execution is enabled in configuration; live Db2 execution remains unverified.";
  }
}

export default function ApprovalsPage() {
  const approvals = useAsync<ApprovalListResponse>(() => api.approvals());
  const [actionType, setActionType] = useState<"runstats" | "create_index">("runstats");
  const [schema, setSchema] = useState("APP");
  const [table, setTable] = useState("DEMO_SERVERS");
  const [column, setColumn] = useState("HOSTNAME");
  const [rationale, setRationale] = useState("Refresh optimizer statistics for review.");
  const [working, setWorking] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function propose(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setWorking("proposal");
    setFormError(null);
    setMessage(null);
    const params: Record<string, string> = { schema, table };
    if (actionType === "create_index") params.column = column;
    try {
      const result = await api.proposeActions({
        actions: [{ action_type: actionType, params, rationale }],
      });
      setMessage(`Created pending approval ${result.approvals[0].id}. No action was executed.`);
      await approvals.reload();
    } catch (error) {
      setFormError(errorMessage(error));
    } finally {
      setWorking(null);
    }
  }

  async function decide(approval: Approval, decision: "approve" | "reject") {
    setWorking(approval.id);
    setFormError(null);
    setMessage(null);
    try {
      const result = await api.decideApproval(approval.id, decision);
      const completed = result.approval;
      if (decision === "reject") {
        setMessage(`Approval ${approval.id} rejected.`);
      } else if (completed.execution?.simulated) {
        setMessage(`Approval ${approval.id} approved: mock simulation only; no Db2 action was executed.`);
      } else if (completed.status === "APPROVED") {
        setMessage(`Approval ${approval.id} recorded; action was not executed (${completed.execution?.reason ?? "execution unavailable"}).`);
      } else {
        setMessage(`Approval ${approval.id}: ${completed.status}. ${completed.execution?.detail ?? ""}`);
      }
      await approvals.reload();
    } catch (error) {
      setFormError(errorMessage(error));
    } finally {
      setWorking(null);
    }
  }

  return (
    <div className="page">
      <PageHeader
        title="Action approvals"
        subtitle="Deterministic, allow-listed maintenance proposals. Every action requires an explicit decision."
        actions={
          <button type="button" className="btn" onClick={() => void approvals.reload()} disabled={approvals.loading}>
            Refresh
          </button>
        }
      />

      {approvals.data && (
        <div className="notice" role="status">{modeMessage(approvals.data.execution_mode)}</div>
      )}
      {formError && <ErrorBanner message={formError} />}
      {message && <div className="success-banner" role="status">{message}</div>}

      <section className="card">
        <div className="card-header">
          <h2>Propose a maintenance action</h2>
          <StatusBadge status="neutral" label="proposal only" />
        </div>
        <form className="approval-form" onSubmit={(event) => void propose(event)}>
          <label>
            Action
            <select className="chat-mode" value={actionType} onChange={(event) => setActionType(event.target.value as "runstats" | "create_index")}>
              <option value="runstats">Collect table statistics</option>
              <option value="create_index">Create a single-column index</option>
            </select>
          </label>
          <label>
            Schema
            <input className="approval-input" required value={schema} onChange={(event) => setSchema(event.target.value)} />
          </label>
          <label>
            Table
            <input className="approval-input" required value={table} onChange={(event) => setTable(event.target.value)} />
          </label>
          {actionType === "create_index" && (
            <label>
              Column
              <input className="approval-input" required value={column} onChange={(event) => setColumn(event.target.value)} />
            </label>
          )}
          <label className="approval-form-wide">
            Rationale
            <input className="approval-input" required maxLength={1000} value={rationale} onChange={(event) => setRationale(event.target.value)} />
          </label>
          <button type="submit" className="btn btn-primary" disabled={working !== null}>
            {working === "proposal" ? "Creating…" : "Create pending approval"}
          </button>
        </form>
      </section>

      <section className="card">
        <div className="card-header">
          <h2>Pending approvals</h2>
          {approvals.data && <StatusBadge status="neutral" label={`${approvals.data.total} pending`} />}
        </div>
        {approvals.loading && !approvals.data ? (
          <Spinner label="Loading pending approvals…" />
        ) : approvals.error ? (
          <ErrorBanner message={approvals.error} onRetry={() => void approvals.reload()} />
        ) : approvals.data?.approvals.length ? (
          <div className="approval-list">
            {approvals.data.approvals.map((approval) => (
              <article className="approval-card" key={approval.id}>
                <div className="card-header">
                  <div>
                    <h3>{approval.title}</h3>
                    <span className="meta-text">{approval.id} · {approval.action_type} · {approval.risk} risk</span>
                  </div>
                  <StatusBadge status="warn" label={approval.status} />
                </div>
                <p>{approval.rationale}</p>
                <pre className="msg-sql">{approval.statement}</pre>
                <p className="meta-text">Expires {new Date(approval.expires_at).toLocaleString()}</p>
                <div className="page-actions">
                  <button type="button" className="btn btn-primary" disabled={working !== null} onClick={() => void decide(approval, "approve")}>
                    {working === approval.id ? "Processing…" : "Approve"}
                  </button>
                  <button type="button" className="btn" disabled={working !== null} onClick={() => void decide(approval, "reject")}>
                    Reject
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState title="No pending approvals" hint="Create a proposal above; it will remain pending until you explicitly approve or reject it." />
        )}
      </section>
    </div>
  );
}
