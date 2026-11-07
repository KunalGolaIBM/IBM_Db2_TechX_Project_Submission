import { FileSearch, Files, ScanText } from "lucide-react";

const STEPS = [
  {
    icon: Files,
    number: "01",
    title: "Add the paper",
    body: "Upload the paper your summary refers to. AEGIS keeps the page and passage for every excerpt.",
  },
  {
    icon: ScanText,
    number: "02",
    title: "Add the claim",
    body: "Paste a sentence or a full AI-generated summary. It becomes atomic claims.",
  },
  {
    icon: FileSearch,
    number: "03",
    title: "Inspect the evidence",
    body: "See whether the paper supports, contradicts, or fails to establish each claim.",
  },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" className="scroll-mt-20 border-t border-line py-20 sm:py-24">
      <div className="shell">
        <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
          <div>
            <p className="eyebrow">How it works</p>
            <h2 className="display mt-3 max-w-xl text-[34px] text-ink sm:text-[44px]">
              Three steps. One honest answer.
            </h2>
          </div>
          <p className="max-w-sm text-[14px] leading-6 text-muted">
            No prompt engineering. No black-box score. The evidence is always visible.
          </p>
        </div>

        <div className="mt-12 grid gap-px overflow-hidden rounded-2xl border border-line bg-line sm:grid-cols-3">
          {STEPS.map(({ icon: Icon, number, title, body }) => (
            <div key={number} className="bg-surface p-7 sm:p-8">
              <div className="flex items-center justify-between">
                <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-surface-2">
                  <Icon className="h-4 w-4 text-accent" aria-hidden="true" />
                </span>
                <span className="font-mono text-[10px] tracking-[0.16em] text-muted">{number}</span>
              </div>
              <h3 className="mt-7 text-[16px] font-semibold tracking-[-0.01em] text-ink">{title}</h3>
              <p className="mt-2 text-[13px] leading-6 text-muted">{body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
