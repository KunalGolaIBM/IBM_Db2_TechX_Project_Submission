import { Link } from 'react-router-dom';
import { ArrowLeft, Compass } from 'lucide-react';
import { SectionHeader } from '../components/ui/bits';

export function NotFound() {
  return (
    <div>
      <SectionHeader
        eyebrow="Navigation"
        title="Sector not found"
        description="That command view does not exist in this build."
      />
      <div className="panel flex flex-col items-start gap-4 p-8">
        <Compass className="h-8 w-8 text-accent" />
        <p className="text-sm leading-relaxed text-slate-400">
          Return to the command overview to continue monitoring the grid.
        </p>
        <Link
          to="/"
          className="inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-950 shadow-glow transition hover:bg-accent-bright"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Command overview
        </Link>
      </div>
    </div>
  );
}
