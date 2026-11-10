import { riskStyle } from '../../lib/format';

const RISK_PROGRESS: Record<string, number> = {
  HIGH: 0.92,
  MODERATE: 0.6,
  LOW: 0.26,
};

function progressFor(risk: string | null | undefined): number {
  const key = (risk ?? '').toUpperCase();
  return RISK_PROGRESS[key] ?? 0;
}

export function RiskDial({
  risk,
  size = 190,
  caption,
}: {
  risk: string | null | undefined;
  size?: number;
  caption?: string;
}) {
  const style = riskStyle(risk);
  const pending = style.label === 'PENDING';
  const radius = 76;
  const circumference = 2 * Math.PI * radius;
  const arcLength = circumference * 0.75;
  const progress = pending ? 0 : progressFor(risk);
  const valueLength = arcLength * progress;

  return (
    <div
      className="relative shrink-0"
      style={{ width: size, height: size }}
      role="img"
      aria-label={`Overall grid risk: ${style.label}`}
    >
      <svg viewBox="0 0 200 200" className="h-full w-full -rotate-0">
        <circle
          cx="100"
          cy="100"
          r={radius}
          fill="none"
          stroke="#141C2E"
          strokeWidth="12"
          strokeLinecap="round"
          strokeDasharray={`${arcLength} ${circumference}`}
          transform="rotate(135 100 100)"
        />
        <circle
          cx="100"
          cy="100"
          r={radius}
          fill="none"
          stroke={pending ? '#334155' : style.color}
          strokeWidth="12"
          strokeLinecap="round"
          strokeDasharray={pending ? undefined : `${valueLength} ${circumference}`}
          strokeDashoffset={0}
          transform="rotate(135 100 100)"
          opacity={pending ? 0.55 : 1}
          style={{
            transition: 'stroke-dasharray 700ms cubic-bezier(0.22,1,0.36,1)',
            filter: pending ? undefined : `drop-shadow(0 0 8px ${style.color}66)`,
          }}
        />
        {[0, 0.25, 0.5, 0.75, 1].map((step) => {
          const angle = (135 + step * 270) * (Math.PI / 180);
          const inner = radius - 18;
          const outer = radius - 12;
          return (
            <line
              key={step}
              x1={100 + Math.cos(angle) * inner}
              y1={100 + Math.sin(angle) * inner}
              x2={100 + Math.cos(angle) * outer}
              y2={100 + Math.sin(angle) * outer}
              stroke="#334155"
              strokeWidth="2"
            />
          );
        })}
      </svg>

      <div className="absolute inset-0 flex flex-col items-center justify-center pt-1">
        <span
          className={`font-display text-[26px] font-bold leading-none tracking-tight ${style.textClass}`}
        >
          {pending ? '—' : style.label}
        </span>
        <span className="mt-2 text-[9px] font-semibold uppercase tracking-[0.2em] text-slate-500">
          {pending ? 'Awaiting analysis' : 'Overall risk'}
        </span>
        {caption ? (
          <span className="mt-1.5 max-w-[130px] text-center text-[9px] leading-tight text-slate-600">
            {caption}
          </span>
        ) : null}
      </div>
    </div>
  );
}
