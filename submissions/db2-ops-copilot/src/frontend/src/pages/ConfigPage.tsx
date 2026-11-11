import { api } from "../api/client";
import type { AuditResponse, ConfigResponse } from "../api/types";
import { ErrorBanner, PageHeader, Spinner, StatusBadge } from "../components/Ui";
import { useAsync } from "../hooks/useAsync";

export default function ConfigPage() {
  const config = useAsync<ConfigResponse>(() => api.config());
  const audit = useAsync<AuditResponse>(() => api.audit(10));

  return (
    <div className="page">
      <PageHeader
        title="Configuration"
        subtitle="Effective non-secret runtime configuration. Secrets are never exposed by the API."
        actions={
          <button
            type="button"
            className="btn"
            onClick={() => {
              void config.reload();
              void audit.reload();
            }}
          >
            Refresh
          </button>
        }
      />

      {config.loading && !config.data ? (
        <Spinner label="Loading configuration…" />
      ) : config.error ? (
        <ErrorBanner message={config.error} onRetry={() => void config.reload()} />
      ) : (
        config.data && <ConfigSections config={config.data} />
      )}

      <section className="card">
        <div className="card-header">
          <h2>Recent audit entries</h2>
          {audit.data && (
            <StatusBadge
              status="neutral"
              label={audit.data.mock ? "mock store" : "db2 APP_AUDIT"}
            />
          )}
        </div>
        {audit.loading && !audit.data ? (
          <Spinner label="Loading audit trail…" />
        ) : audit.error ? (
          <ErrorBanner message={audit.error} onRetry={() => void audit.reload()} />
        ) : audit.data && audit.data.entries.length === 0 ? (
          <p className="meta-text">No audit entries yet — ask something in the chat workspace.</p>
        ) : (
          audit.data && (
            <table className="table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Time</th>
                  <th>Intent</th>
                  <th>Question</th>
                  <th>Status</th>
                  <th>ms</th>
                </tr>
              </thead>
              <tbody>
                {audit.data.entries.map((entry) => (
                  <tr key={entry.id}>
                    <td>{entry.id}</td>
                    <td className="nowrap">{entry.timestamp.slice(11, 19)}</td>
                    <td>{entry.intent}</td>
                    <td className="truncate" title={entry.question}>
                      {entry.question}
                    </td>
                    <td>
                      <StatusBadge
                        status={
                          entry.status === "OK"
                            ? "ok"
                            : entry.status === "BLOCKED"
                              ? "error"
                              : "warn"
                        }
                        label={entry.status}
                      />
                    </td>
                    <td>{entry.latency_ms}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        )}
      </section>
    </div>
  );
}

function ConfigSections({ config }: { config: ConfigResponse }) {
  return (
    <div className="card-grid">
      <section className="card">
        <div className="card-header">
          <h2>Application</h2>
          <StatusBadge status="neutral" label={config.environment} />
        </div>
        <dl className="kv-list">
          <Row k="Adapter mode" v={config.adapter_mode} />
          <Row k="Debug" v={config.debug ? "true" : "false"} />
          <Row k="API base" v={config.api_base} />
          <Row k="CORS origins" v={config.cors_origins.join(", ") || "—"} />
          <Row k="Serves frontend" v={config.serve_frontend ? "yes" : "no"} />
        </dl>
      </section>

      <section className="card">
        <div className="card-header">
          <h2>Database</h2>
          <StatusBadge status="neutral" label="read-only account" />
        </div>
        <dl className="kv-list">
          <Row k="Host" v={config.database.host} />
          <Row k="Port" v={String(config.database.port)} />
          <Row k="Database" v={config.database.name} />
          <Row k="Read-only user" v={config.database.read_only_user} />
        </dl>
      </section>

      <section className="card">
        <div className="card-header">
          <h2>Models</h2>
        </div>
        <dl className="kv-list">
          <Row k="Chat model" v={config.models.llm} />
          <Row k="Embedding model" v={config.models.embeddings} />
          <Row k="Ollama URL" v={config.models.ollama_base_url} />
        </dl>
      </section>

      <section className="card">
        <div className="card-header">
          <h2>SQL policy</h2>
          <StatusBadge
            status="ok"
            label={config.sql_policy.allowed_statements.join("/")}
          />
        </div>
        <dl className="kv-list">
          <Row k="Max rows" v={String(config.sql_policy.max_rows)} />
          <Row k="Query timeout" v={`${config.sql_policy.query_timeout_ms} ms`} />
          <Row k="Max SQL length" v={String(config.sql_policy.max_sql_length)} />
          <Row k="Max AST nodes" v={String(config.sql_policy.max_ast_nodes)} />
          <Row
            k="Denied schemas"
            v={config.sql_policy.denied_schemas.join(", ")}
          />
          <Row
            k="Row-limit enforced"
            v={config.sql_policy.enforce_row_limit ? "yes" : "no"}
          />
        </dl>
      </section>

      <section className="card">
        <div className="card-header">
          <h2>Security</h2>
        </div>
        <dl className="kv-list">
          <Row k="Prompt-injection mode" v={config.security.injection_mode} />
          <Row
            k="Max message length"
            v={String(config.security.max_message_length)}
          />
        </dl>
      </section>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="kv-row">
      <dt>{k}</dt>
      <dd>{v}</dd>
    </div>
  );
}
