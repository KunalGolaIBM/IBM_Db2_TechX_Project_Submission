import type { ReactNode } from "react";
import { api } from "../api/client";
import type { HealthResponse, StatusResponse } from "../api/types";
import { ErrorBanner, PageHeader, Spinner, StatusBadge } from "../components/Ui";
import { useAsync } from "../hooks/useAsync";

function statusKind(status: boolean | string): "ok" | "warn" | "error" {
  if (status === true || status === "ok") return "ok";
  if (status === "degraded") return "warn";
  return "error";
}

export default function Dashboard() {
  const health = useAsync<HealthResponse>(() => api.health());
  const status = useAsync<StatusResponse>(() => api.status());

  return (
    <div className="page">
      <PageHeader
        title="Dashboard"
        subtitle="Live dependency status — every check probes the configured adapters."
        actions={
          <button
            type="button"
            className="btn"
            onClick={() => {
              void health.reload();
              void status.reload();
            }}
            disabled={health.loading || status.loading}
          >
            Refresh
          </button>
        }
      />

      {health.error && (
        <ErrorBanner message={health.error} onRetry={() => void health.reload()} />
      )}

      {health.loading && !health.data ? (
        <Spinner label="Probing services…" />
      ) : (
        health.data && (
          <section className="card">
            <div className="card-header">
              <h2>Application</h2>
              <div className="card-header-meta">
                <StatusBadge
                  status={statusKind(health.data.status)}
                  label={health.data.status}
                />
                <StatusBadge
                  status="neutral"
                  label={`mode: ${health.data.mode}`}
                />
                <span className="meta-text">
                  v{health.data.version} · up {Math.floor(health.data.uptime_seconds)}s
                </span>
              </div>
            </div>
            <div className="probe-grid">
              {health.data.checks.map((check) => (
                <div key={check.name} className="probe-row">
                  <div className="probe-name">
                    <StatusBadge
                      status={statusKind(check.status)}
                      label={check.status}
                    />
                    <span>{check.name}</span>
                  </div>
                  <div className="probe-detail">{check.detail}</div>
                  <div className="meta-text">{check.latency_ms.toFixed(1)} ms</div>
                </div>
              ))}
            </div>
          </section>
        )
      )}

      {status.loading && !status.data && !status.error ? (
        <Spinner label="Loading service status…" />
      ) : status.error ? (
        <ErrorBanner message={status.error} onRetry={() => void status.reload()} />
      ) : (
        status.data && (
          <div className="card-grid">
            <InfoCard
              title="Database"
              badge={
                <StatusBadge
                  status={statusKind(status.data.database.connected)}
                  label={
                    status.data.database.connected ? "connected" : "unavailable"
                  }
                />
              }
              rows={[
                ["Provider", status.data.database.provider],
                ["Target", `${status.data.database.host}:${status.data.database.port}`],
                ["Database", status.data.database.database],
                ["Detail", status.data.database.detail],
              ]}
            />
            <InfoCard
              title="Vector store"
              badge={
                <StatusBadge
                  status="neutral"
                  label={`${status.data.vector_store.document_count} docs`}
                />
              }
              rows={[
                ["Provider", status.data.vector_store.provider],
                ["Detail", status.data.vector_store.detail],
              ]}
            />
            <InfoCard
              title="Chat model"
              badge={
                <StatusBadge
                  status={statusKind(status.data.llm.available)}
                  label={status.data.llm.available ? "available" : "unavailable"}
                />
              }
              rows={[
                ["Model", status.data.llm.model],
                ["Provider", status.data.llm.provider],
                ["Detail", status.data.llm.detail],
              ]}
            />
            <InfoCard
              title="Embeddings"
              badge={
                <StatusBadge
                  status={statusKind(status.data.embeddings.available)}
                  label={
                    status.data.embeddings.available ? "available" : "unavailable"
                  }
                />
              }
              rows={[
                ["Model", status.data.embeddings.model],
                [
                  "Dimensions",
                  status.data.embeddings.dimensions?.toString() ?? "—",
                ],
                ["Detail", status.data.embeddings.detail],
              ]}
            />
          </div>
        )
      )}
    </div>
  );
}

function InfoCard({
  title,
  badge,
  rows,
}: {
  title: string;
  badge: ReactNode;
  rows: [string, string][];
}) {
  return (
    <section className="card">
      <div className="card-header">
        <h2>{title}</h2>
        {badge}
      </div>
      <dl className="kv-list">
        {rows.map(([key, value]) => (
          <div key={key} className="kv-row">
            <dt>{key}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
