import { BrainCircuit, FileSearch, Gavel, History } from 'lucide-react';
import EmptyState from '../common/EmptyState';
import { DECISION_META } from '../../utils/constants';
import { cx, formatDateTime } from '../../utils/formatters';
import type { Decision, TimelineEvent } from '../../types';

interface VendorTimelineProps {
  events: TimelineEvent[];
}

const DECIDED_TONE: Record<Decision, string> = {
  APPROVED: 'bg-emerald-100 text-emerald-600',
  REJECTED: 'bg-red-100 text-red-600',
  NEEDS_REVIEW: 'bg-blue-100 text-blue-600',
};

function Badge({ decision, prefix }: { decision: Decision; prefix?: string }) {
  return (
    <span className={cx('rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ring-inset', DECISION_META[decision].badge)}>
      {prefix}
      {DECISION_META[decision].label}
    </span>
  );
}

export default function VendorTimeline({ events }: VendorTimelineProps) {
  if (events.length === 0) {
    return (
      <EmptyState
        compact
        icon={History}
        title="No activity yet"
        description="Processed invoices and reviewer decisions for this vendor appear here, newest first."
      />
    );
  }

  const newestFirst = [...events].reverse();

  return (
    <ol className="relative space-y-6 before:absolute before:bottom-3 before:left-[17px] before:top-3 before:w-px before:bg-slate-200">
      {newestFirst.map((event, index) => {
        const decided = event.event === 'decided';
        const Icon = decided ? Gavel : FileSearch;
        return (
          <li key={`${event.timestamp}-${event.invoice_id}-${index}`} className="relative flex gap-4">
            <span
              className={cx(
                'relative z-10 flex h-9 w-9 shrink-0 items-center justify-center rounded-full ring-4 ring-white',
                decided && event.decision ? DECIDED_TONE[event.decision] : 'bg-slate-100 text-slate-600',
              )}
            >
              <Icon className="h-4 w-4" aria-hidden="true" />
            </span>
            <div className="min-w-0 flex-1 pt-1">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-sm font-semibold text-slate-900">
                  {decided ? 'Reviewer decided' : 'Agent reviewed'} <span className="font-mono">{event.invoice_id}</span>
                </p>
                {decided && event.decision && <Badge decision={event.decision} />}
                {!decided && event.recommendation && <Badge decision={event.recommendation} prefix="Recommended " />}
              </div>
              <p className={cx('mt-1 break-words text-sm', decided ? 'italic text-slate-700' : 'text-slate-600')}>
                {decided ? `“${event.detail}”` : event.detail}
              </p>
              {decided && event.retained !== null && (
                <span
                  className={cx(
                    'mt-2 inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium',
                    event.retained ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-600',
                  )}
                >
                  <BrainCircuit className="h-3.5 w-3.5" aria-hidden="true" />
                  {event.retained ? 'Remembered in Hindsight' : 'Not stored in Hindsight'}
                </span>
              )}
              <time className="mt-1.5 block text-xs text-slate-400" dateTime={event.timestamp}>
                {formatDateTime(event.timestamp)}
              </time>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
