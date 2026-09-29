import { BrainCircuit, CalendarDays, Sparkles, WifiOff } from 'lucide-react';
import BentoCard from '../common/BentoCard';
import EmptyState from '../common/EmptyState';
import { DECISION_META } from '../../utils/constants';
import { cx, formatCurrency, formatDateTime, formatExceptionValue, humanize } from '../../utils/formatters';
import type { HindsightMemory, MemoryStatus } from '../../types';

interface HindsightMemoriesCardProps {
  memories: HindsightMemory[];
  reflection: string | null;
  memoryStatus: MemoryStatus;
  vendor: string;
  className?: string;
}

function MemoryItem({ memory }: { memory: HindsightMemory }) {
  const isPrice = memory.exception_type === 'PRICE_MISMATCH';
  const invoiced = isPrice ? formatCurrency(memory.invoice_price) : formatExceptionValue(memory.exception_type, memory.actual_value);
  const onPo = isPrice ? formatCurrency(memory.po_price) : formatExceptionValue(memory.exception_type, memory.expected_value);

  return (
    <li className="animate-slide-up rounded-xl border border-slate-200 bg-slate-50/60 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-slate-900">
            {humanize(memory.exception_type)}
            {memory.invoice_id && <span className="font-mono font-normal text-slate-500"> · {memory.invoice_id}</span>}
          </p>
          <p className="text-xs text-slate-500">{memory.vendor}</p>
        </div>
        <span className={cx('rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset', DECISION_META[memory.decision].badge)}>
          {DECISION_META[memory.decision].label}
        </span>
      </div>

      <p className="tabular mt-3 text-sm text-slate-700">
        Invoiced <span className="font-semibold text-slate-900">{invoiced}</span> against a PO of{' '}
        <span className="font-semibold text-slate-900">{onPo}</span>
      </p>

      {memory.human_reason && (
        <blockquote className="mt-3 border-l-2 border-violet-300 pl-3 text-sm italic text-slate-700">“{memory.human_reason}”</blockquote>
      )}

      <p className="mt-3 text-xs leading-relaxed text-slate-500">
        <span className="font-semibold text-slate-600">Hindsight recalled:</span> {memory.text}
      </p>
      {memory.created_at && (
        <p className="mt-2 flex items-center gap-1.5 text-xs text-slate-400">
          <CalendarDays className="h-3.5 w-3.5" aria-hidden="true" />
          Decided {formatDateTime(memory.created_at)}
        </p>
      )}
    </li>
  );
}

export default function HindsightMemoriesCard({ memories, reflection, memoryStatus, vendor, className = '' }: HindsightMemoriesCardProps) {
  const subtitle =
    memoryStatus === 'unavailable'
      ? 'Memory offline for this invoice'
      : memories.length > 0
        ? `${memories.length} verified decision${memories.length === 1 ? '' : 's'} for ${vendor}`
        : `Nothing on file for ${vendor} yet`;

  return (
    <BentoCard
      className={className}
      hoverable={false}
      icon={<BrainCircuit className="h-5 w-5" aria-hidden="true" />}
      title="Hindsight memory"
      subtitle={subtitle}
    >
      {memoryStatus === 'unavailable' ? (
        <EmptyState
          compact
          tone="warning"
          icon={WifiOff}
          title="Memory offline"
          description="Hindsight wasn't available, so no past decisions were checked. The System panel shows why (not configured, unreachable, or a key, credit or bank problem)."
        />
      ) : memories.length === 0 ? (
        <EmptyState
          compact
          icon={BrainCircuit}
          title="No prior vendor-specific memory found"
          description={`Memory is per vendor: decisions about other vendors are never used for ${vendor}. Your decision on this invoice becomes its first memory.`}
        />
      ) : (
        <ul className="space-y-3">
          {memories.map((memory, index) => (
            <MemoryItem key={`${memory.invoice_id ?? 'memory'}-${memory.exception_type}-${index}`} memory={memory} />
          ))}
        </ul>
      )}

      {reflection && (
        <div className="mt-4 rounded-xl bg-gradient-to-br from-violet-50 to-blue-50 p-4 ring-1 ring-inset ring-violet-100">
          <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-violet-700">
            <Sparkles className="h-4 w-4" aria-hidden="true" />
            Hindsight reflection
          </p>
          <p className="mt-2 whitespace-pre-line text-sm leading-relaxed text-slate-700">{reflection}</p>
        </div>
      )}
    </BentoCard>
  );
}
