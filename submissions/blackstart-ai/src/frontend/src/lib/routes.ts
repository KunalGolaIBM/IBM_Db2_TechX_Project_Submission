import {
  Activity,
  Bot,
  FlaskConical,
  HeartPulse,
  LayoutDashboard,
  Network,
  ShieldCheck,
  Siren,
  type LucideIcon,
} from 'lucide-react';

export interface RouteMeta {
  path: string;
  label: string;
  shortLabel: string;
  description: string;
  icon: LucideIcon;
}

export const ROUTES: RouteMeta[] = [
  {
    path: '/',
    label: 'Command Overview',
    shortLabel: 'Overview',
    description: 'Executive grid posture across plants, substations, lines and incidents.',
    icon: LayoutDashboard,
  },
  {
    path: '/infrastructure',
    label: 'Grid Infrastructure',
    shortLabel: 'Infrastructure',
    description: 'Power plants, substations, transmission lines and network topology.',
    icon: Network,
  },
  {
    path: '/incidents',
    label: 'Incident Intelligence',
    shortLabel: 'Incidents',
    description: 'Open grid incidents sourced directly from IBM Db2.',
    icon: Siren,
  },
  {
    path: '/agents',
    label: 'Agent Intelligence',
    shortLabel: 'Agents',
    description: 'The five-agent LangGraph pipeline and its returned findings.',
    icon: Bot,
  },
  {
    path: '/cascade',
    label: 'Cascade Simulation',
    shortLabel: 'Cascade',
    description: 'Transmission utilization bands and demonstration cascade risk.',
    icon: FlaskConical,
  },
  {
    path: '/recovery',
    label: 'Recovery Recommendations',
    shortLabel: 'Recovery',
    description: 'Advisory-only recommendations requiring human operator review.',
    icon: ShieldCheck,
  },
  {
    path: '/health',
    label: 'System Health',
    shortLabel: 'Health',
    description: 'FastAPI, IBM Db2, API connectivity and analysis history.',
    icon: HeartPulse,
  },
];

export function routeMeta(pathname: string): RouteMeta {
  return ROUTES.find((route) => route.path === pathname) ?? ROUTES[0];
}

export const PIPELINE_AGENTS = [
  { key: 'volt', name: 'VOLT', role: 'Incident Intelligence', icon: Activity },
  { key: 'pulse', name: 'PULSE', role: 'Grid Topology Intelligence', icon: Network },
  { key: 'cascade', name: 'CASCADE', role: 'Failure Propagation Intelligence', icon: FlaskConical },
  { key: 'guardian', name: 'GUARDIAN', role: 'Infrastructure Impact Intelligence', icon: ShieldCheck },
  { key: 'blackstart', name: 'BLACKSTART', role: 'Recovery Intelligence', icon: Bot },
] as const;
