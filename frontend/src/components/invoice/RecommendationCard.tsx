import { CircleCheck, CircleHelp, CircleX, ShieldAlert, ShieldCheck, WifiOff } from 'lucide-react';
import BentoCard from '../common/BentoCard';
import { DECISION_META, EVIDENCE_META } from '../../utils/constants';
import { cx, formatPercent } from '../../utils/formatters';
import type { Decision, RecommendationResult } from '../../types';

interface RecommendationCardProps {
  result: RecommendationResult;
  className?: string;
}

const LOOK: Record<Decision, { from: string; to: string; bar: string; icon: typeof CircleCheck; iconClass: string }> = {
  APPROVED: { from: 'from-emerald-50', to: 'to-teal-50', bar: 'from-emerald-500 to-teal-500', icon: CircleCheck, iconClass: 'text-emerald-600' },
  REJECTED: { from: 'from-red-50', to: 'to-orange-50', bar: 'from-red-500 to-orange-500', icon: CircleX, iconClass: 'text-red-600' },
  NEEDS_REVIEW: { from: 'from-blue-50', to: 'to-violet-50', bar: 'from-blue-500 to-violet-500', icon: CircleHelp, iconClass: 'text-blue-600' },
};

export default function RecommendationCard({ result, className = '' }: RecommendationCardProps) {
  const look = LOOK[result.recommendation];
  const Icon = look.icon;
  const evidence = EVIDENCE_META[result.evidence_level];
  const verified = result.evidence_level === 'VERIFIED_MATCH' || result.evidence_level === 'NOT_REQUIRED';
  const EvidenceIcon = verified ? ShieldCheck : ShieldAlert;

  return (
    <BentoCard gradient gradientFrom={look.from} gradientTo={look.to} hoverable={false} className={cx('animate-slide-up', className)}>
      <div aria-live="polite">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Agent recommendation</h2>
          <span className={cx('rounded-full px-3 py-1 text-xs font-semibold ring-1 ring-inset', DECISION_META[result.recommendation].badge)}>
            {DECISION_META[result.recommendation].label}
          </span>
        </div>

        <div className="mt-3 flex items-center gap-3">
          <Icon className={cx('h-9 w-9 shrink-0', look.iconClass)} aria-hidden="true" />
          <p className="text-2xl font-bold tracking-tight text-slate-900">{DECISION_META[result.recommendation].label}</p>
        </div>

        <div className="mt-4">
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium text-slate-600">Confidence</span>
            <span className="tabular font-semibold text-slate-900">{formatPercent(result.confidence)}</span>
          </div>
          <div
            className="mt-1.5 h-2 overflow-hidden rounded-full bg-white/80 ring-1 ring-inset ring-slate-200"
            role="meter"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(result.confidence * 100)}
            aria-label="Confidence"
          >
            <div className={cx('bar-grow h-full rounded-full bg-gradient-to-r', look.bar)} style={{ width: formatPercent(result.confidence) }} />
          </div>
        </div>

        {result.memory_status === 'unavailable' && (
          <div className="mt-4 flex gap-2.5 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
            <WifiOff className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" aria-hidden="true" />
            <p>
              <span className="font-semibold">Memory offline.</span> Hindsight wasn't available (not configured, unreachable or out of
              credits), so no history was checked. This is not the same as "no memory found".
            </p>
          </div>
        )}

        <div className="mt-4 rounded-xl bg-white/70 p-3 ring-1 ring-inset ring-slate-200/70">
          <div className="flex items-center gap-2">
            <EvidenceIcon className={cx('h-4 w-4', verified ? 'text-emerald-600' : 'text-slate-500')} aria-hidden="true" />
            <span className={cx('rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ring-inset', evidence.badge)}>{evidence.label}</span>
          </div>
          <p className="mt-1.5 text-xs text-slate-600">{evidence.meaning}</p>
        </div>

        <h3 className="mt-5 text-sm font-semibold text-slate-900">Why</h3>
        <p className="mt-1 whitespace-pre-line text-sm leading-relaxed text-slate-700">{result.explanation}</p>

        <p className="mt-5 border-t border-slate-200/70 pt-3 text-xs text-slate-500">
          The agent never approves on its own. Your decision below is final, and your reason is what Hindsight remembers.
        </p>
      </div>
    </BentoCard>
  );
}
