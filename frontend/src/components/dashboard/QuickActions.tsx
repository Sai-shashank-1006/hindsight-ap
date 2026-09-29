import { Link } from 'react-router-dom';
import { BookOpen, BrainCircuit, ChevronRight, FilePlus2, FileSearch, Zap, type LucideIcon } from 'lucide-react';
import BentoCard from '../common/BentoCard';
import { API_BASE_URL } from '../../utils/constants';

interface QuickActionsProps {
  pending: number;
  className?: string;
}

interface Action {
  label: string;
  description: string;
  icon: LucideIcon;
  to?: string;
  href?: string;
  accent: string;
}

export default function QuickActions({ pending, className = '' }: QuickActionsProps) {
  const actions: Action[] = [
    {
      label: 'Review next invoice',
      description: pending > 0 ? `${pending} awaiting a decision` : 'Work through the queue',
      icon: FileSearch,
      to: '/review',
      accent: 'from-blue-500 to-violet-600',
    },
    {
      label: 'Enter an invoice',
      description: 'Type one in or upload a JSON file',
      icon: FilePlus2,
      to: '/review?mode=manual',
      accent: 'from-emerald-500 to-teal-500',
    },
    {
      label: 'Vendor memory',
      description: 'What the agent has learned per vendor',
      icon: BrainCircuit,
      to: '/vendors',
      accent: 'from-violet-500 to-fuchsia-500',
    },
    {
      label: 'API docs',
      description: 'The FastAPI backend, interactive',
      icon: BookOpen,
      href: `${API_BASE_URL}/docs`,
      accent: 'from-slate-600 to-slate-800',
    },
  ];

  const row = (action: Action) => (
    <>
      <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br text-white shadow-sm ${action.accent}`}>
        <action.icon className="h-4 w-4" aria-hidden="true" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-semibold text-slate-900">{action.label}</span>
        <span className="block text-xs leading-snug text-slate-500">{action.description}</span>
      </span>
      <ChevronRight className="h-4 w-4 shrink-0 text-slate-300 transition-transform group-hover:translate-x-0.5 group-hover:text-slate-500" aria-hidden="true" />
    </>
  );
  const itemClass = 'group flex items-center gap-3 rounded-xl p-2.5 transition-colors hover:bg-slate-50';

  return (
    <BentoCard className={className} hoverable={false} icon={<Zap className="h-5 w-5" aria-hidden="true" />} title="Quick actions">
      <ul className="-mx-1 space-y-1">
        {actions.map((action) => (
          <li key={action.label}>
            {action.to ? (
              <Link to={action.to} className={itemClass}>
                {row(action)}
              </Link>
            ) : (
              <a href={action.href} target="_blank" rel="noreferrer" className={itemClass}>
                {row(action)}
              </a>
            )}
          </li>
        ))}
      </ul>
    </BentoCard>
  );
}
