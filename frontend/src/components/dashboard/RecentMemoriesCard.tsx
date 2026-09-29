import { Link } from 'react-router-dom';
import { ArrowRight, BrainCircuit, Quote } from 'lucide-react';
import BentoCard from '../common/BentoCard';
import EmptyState from '../common/EmptyState';
import GradientButton from '../common/GradientButton';
import { DECISION_META } from '../../utils/constants';
import { cx, formatDateTime, formatRelativeTime, humanize } from '../../utils/formatters';
import type { MemorySummary } from '../../types';

interface RecentMemoriesCardProps {
  memories: MemorySummary[];
  className?: string;
}

export default function RecentMemoriesCard({ memories, className = '' }: RecentMemoriesCardProps) {
  return (
    <BentoCard
      className={className}
      hoverable={false}
      icon={<BrainCircuit className="h-5 w-5" aria-hidden="true" />}
      title="Recent Hindsight memories"
      subtitle="Human decisions retained for the next matching invoice"
      action={
        <Link to="/vendors" className="inline-flex items-center gap-1 text-sm font-semibold text-blue-600 hover:text-blue-700">
          View all <ArrowRight className="h-4 w-4" aria-hidden="true" />
        </Link>
      }
    >
      {memories.length === 0 ? (
        <EmptyState
          compact
          icon={BrainCircuit}
          title="No memories yet"
          description="Approve or reject an exception with a reason. That decision becomes the first memory."
          action={
            <GradientButton size="sm" to="/review">
              Review an invoice
            </GradientButton>
          }
        />
      ) : (
        <ul className="space-y-3">
          {memories.slice(0, 5).map((memory) => (
            <li
              key={memory.memory_id}
              className="animate-slide-up rounded-xl border border-slate-200 bg-slate-50/60 p-4 transition-colors hover:border-slate-300 hover:bg-white"
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <Link to={`/vendors/${encodeURIComponent(memory.vendor)}`} className="font-semibold text-slate-900 hover:text-blue-700">
                    {memory.vendor}
                  </Link>
                  <p className="mt-0.5 text-xs text-slate-500">
                    {memory.invoice_id} · {memory.exception_types.map(humanize).join(', ') || 'No exception'}
                  </p>
                </div>
                <span className={cx('rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset', DECISION_META[memory.decision].badge)}>
                  {DECISION_META[memory.decision].label}
                </span>
              </div>
              <p className="mt-3 flex gap-2 text-sm text-slate-700">
                <Quote className="mt-0.5 h-4 w-4 shrink-0 text-slate-300" aria-hidden="true" />
                <span className="line-clamp-2">{memory.human_reason}</span>
              </p>
              <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-400">
                <span className="font-mono">{memory.memory_id}</span>
                <time dateTime={memory.created_at} title={formatDateTime(memory.created_at)}>
                  {formatRelativeTime(memory.created_at)}
                </time>
              </div>
            </li>
          ))}
        </ul>
      )}
    </BentoCard>
  );
}
