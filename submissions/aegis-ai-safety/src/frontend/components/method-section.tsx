import { Fingerprint, ShieldAlert, TableProperties } from "lucide-react";

import { ClassificationLegend } from "@/components/classification";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const TABLES = [
  "DOCUMENTS",
  "PASSAGES",
  "VERIFICATION_SESSIONS",
  "CLAIMS",
  "VERIFICATION_RESULTS",
  "EVIDENCE_LINKS",
];

export function MethodSection() {
  return (
    <Card id="method" className="scroll-mt-24">
      <CardHeader>
        <p className="eyebrow">04 / Method</p>
        <CardTitle className="mt-1.5 text-base">How AEGIS reaches a judgment</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-8 lg:grid-cols-2">
        <div className="space-y-5">
          <ClassificationLegend columns={1} />
          <p className="rounded-md border border-border bg-panel-2/50 px-3.5 py-3 text-[11px] leading-5 text-muted">
            AEGIS is an independent verification tool, not a general-purpose chatbot. A relevant
            passage is not automatically supporting evidence, and missing evidence is never
            classified as contradiction.
          </p>
        </div>

        <div className="space-y-5">
          <div className="flex gap-3">
            <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-accent/25 bg-accent-soft">
              <Fingerprint className="h-3.5 w-3.5 text-accent" aria-hidden="true" />
            </span>
            <div>
              <p className="text-xs font-medium text-fg">Evidence-linked by construction</p>
              <p className="mt-1 text-[11px] leading-5 text-muted">
                Every definitive classification must cite a passage ID that was actually retrieved
                from Db2. Fabricated or missing references are downgraded to insufficient evidence.
              </p>
            </div>
          </div>
          <div className="flex gap-3">
            <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-insufficient/25 bg-insufficient/5">
              <ShieldAlert className="h-3.5 w-3.5 text-insufficient" aria-hidden="true" />
            </span>
            <div>
              <p className="text-xs font-medium text-fg">Documents are untrusted data</p>
              <p className="mt-1 text-[11px] leading-5 text-muted">
                Text inside research inputs and evidence is never treated as instructions. Uploads
                are size- and type-validated, and SQL is parameterized throughout.
              </p>
            </div>
          </div>
          <div className="flex gap-3">
            <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-border bg-panel-2">
              <TableProperties className="h-3.5 w-3.5 text-muted" aria-hidden="true" />
            </span>
            <div>
              <p className="text-xs font-medium text-fg">Relational persistence</p>
              <p className="mt-1 text-[11px] leading-5 text-muted">
                Six Db2 tables preserve provenance and reproducibility for every session.
              </p>
              <div className="mt-2 flex flex-wrap gap-1">
                {TABLES.map((table) => (
                  <span
                    key={table}
                    className="rounded border border-border bg-panel-2 px-1.5 py-0.5 font-mono text-[8.5px] text-muted"
                  >
                    {table}
                  </span>
                ))}
              </div>
            </div>
          </div>
          <p className="border-t border-border pt-4 font-mono text-[10px] leading-5 text-muted">
            Evaluation: SciFact loading and metrics utilities are prepared. No benchmark scores are
            reported until the harness is actually executed.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
