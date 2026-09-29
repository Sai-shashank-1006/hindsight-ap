import { TrendingDown, TrendingUp } from 'lucide-react';
import { SEVERITY_META } from '../../utils/constants';
import { cx, formatExceptionValue, formatVariance, humanize } from '../../utils/formatters';
import type { InvoiceException } from '../../types';

interface ExceptionBadgeProps {
  exception: InvoiceException;
  /** Full row with PO vs invoiced values and the rule engine's reason. */
  detailed?: boolean;
}

export default function ExceptionBadge({ exception, detailed = false }: ExceptionBadgeProps) {
  const severity = SEVERITY_META[exception.severity];
  const above = exception.actual_value > exception.expected_value;
  const Trend = above ? TrendingUp : TrendingDown;

  if (!detailed) {
    return (
      <span className={cx('inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset', severity.badge)}>
        <span className={cx('h-1.5 w-1.5 rounded-full', severity.dot)} aria-hidden="true" />
        {humanize(exception.type)} · {formatVariance(exception.variance_percent)}
      </span>
    );
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-semibold text-slate-900">{humanize(exception.type)}</h3>
        <span className={cx('inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset', severity.badge)}>
          <span className={cx('h-1.5 w-1.5 rounded-full', severity.dot)} aria-hidden="true" />
          {severity.label}
        </span>
      </div>
      <dl className="mt-3 grid grid-cols-3 gap-3 text-sm">
        <div>
          <dt className="text-xs text-slate-500">PO record</dt>
          <dd className="tabular font-semibold text-slate-900">{formatExceptionValue(exception.type, exception.expected_value)}</dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">Invoiced</dt>
          <dd className="tabular font-semibold text-slate-900">{formatExceptionValue(exception.type, exception.actual_value)}</dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">Variance</dt>
          <dd className={cx('tabular inline-flex items-center gap-1 font-semibold', above ? 'text-red-600' : 'text-sky-700')}>
            <Trend className="h-4 w-4" aria-hidden="true" />
            {formatVariance(exception.variance_percent)}
          </dd>
        </div>
      </dl>
      <p className="mt-3 text-sm text-slate-600">{exception.reason}</p>
    </div>
  );
}
