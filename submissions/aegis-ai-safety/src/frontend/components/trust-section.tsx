import { ArrowRight, Database, FileText, ShieldCheck, Sparkles } from "lucide-react";

const FLOW = [
  { icon: FileText, label: "Scientific paper" },
  { icon: Database, label: "IBM Db2" },
  { icon: Sparkles, label: "LangChain" },
  { icon: ShieldCheck, label: "Evidence-linked result" },
];

export function TrustSection() {
  return (
    <section className="border-t border-line py-20 sm:py-24">
      <div className="shell">
        <div className="grid gap-10 lg:grid-cols-[0.85fr_1.15fr] lg:items-center">
          <div>
            <p className="eyebrow">Evidence first. Confidence second.</p>
            <h2 className="display mt-3 max-w-md text-[34px] text-ink sm:text-[44px]">
              A verdict without a passage is just an opinion.
            </h2>
            <p className="mt-4 max-w-md text-[14px] leading-6 text-muted">
              Every definitive result cites a passage that was actually retrieved from Db2. If the
              paper does not establish the claim, AEGIS says so.
            </p>
            <p className="mt-5 max-w-md border-l-2 border-line pl-3 text-[11.5px] leading-5 text-muted">
              AEGIS assists research verification. It does not replace expert review. SciFact
              development subset: macro F1 0.678 on 100 claims — not general accuracy.
            </p>
          </div>

          <div className="surface p-5 sm:p-7">
            <div className="flex flex-col items-stretch gap-2 sm:flex-row sm:items-center">
              {FLOW.map(({ icon: Icon, label }, index) => (
                <div key={label} className="flex flex-1 items-center gap-2">
                  <div className="flex flex-1 items-center gap-2.5 rounded-xl border border-line bg-canvas px-3 py-3">
                    <Icon className="h-3.5 w-3.5 shrink-0 text-accent" aria-hidden="true" />
                    <span className="text-[11.5px] font-medium leading-4 text-ink">{label}</span>
                  </div>
                  {index < FLOW.length - 1 ? (
                    <ArrowRight
                      className="hidden h-3.5 w-3.5 shrink-0 text-muted sm:block"
                      aria-hidden="true"
                    />
                  ) : null}
                </div>
              ))}
            </div>
            <div className="mt-6 grid gap-3 border-t border-line pt-5 sm:grid-cols-3">
              {[
                ["6", "Db2 tables"],
                ["Page", "provenance"],
                ["JSON / MD", "export"],
              ].map(([value, label]) => (
                <div key={label}>
                  <p className="text-[17px] font-semibold tracking-[-0.02em] text-ink">{value}</p>
                  <p className="mt-0.5 font-mono text-[9px] uppercase tracking-[0.12em] text-muted">
                    {label}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
