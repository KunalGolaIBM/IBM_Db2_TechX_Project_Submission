import { ReactNode } from 'react';
interface Props { label: string; value: string | number; icon: ReactNode; color?: string; }
export default function StatCard({ label, value, icon, color = 'text-teal-400' }: Props) {
  return (
    <div className="bg-navy-800 border border-navy-600 rounded-xl p-5 flex items-center gap-4">
      <div className={`w-12 h-12 rounded-xl bg-navy-700 flex items-center justify-center ${color}`}>
        {icon}
      </div>
      <div>
        <p className="text-slate-400 text-xs uppercase tracking-wide">{label}</p>
        <p className="text-white text-2xl font-bold mt-0.5">{value}</p>
      </div>
    </div>
  );
}
