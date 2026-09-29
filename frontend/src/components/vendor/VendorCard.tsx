import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import { Line, LineChart, ResponsiveContainer, YAxis } from 'recharts';
import BentoCard from '../common/BentoCard';
import { SEVERITY_META, VENDOR_STATUS_META } from '../../utils/constants';
import { cx, formatCurrency, formatNumber, formatPercent, formatVariance, humanize, initials } from '../../utils/formatters';
import type { VendorProfile } from '../../types';

interface VendorCardProps {
  vendor: VendorProfile;
}

function PriceHistory({ prices }: { prices: number[] }) {
  if (prices.length === 0) return <p className="text-xs text-slate-400">No price history on file</p>;
  const low = Math.min(...prices);
  const high = Math.max(...prices);
  return (
    <div>
      <p className="text-xs text-slate-500">
        Historical prices <span className="tabular font-semibold text-slate-700">{low === high ? formatCurrency(low) : `${formatCurrency(low)} – ${formatCurrency(high)}`}</span>
      </p>
      {prices.length > 1 && (
        <div className="mt-2 h-10" aria-hidden="true">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={prices.map((price, index) => ({ index, price }))} margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
              <YAxis hide domain={['dataMin', 'dataMax']} />
              <Line type="monotone" dataKey="price" stroke="#8b5cf6" strokeWidth={2} dot={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

export default function VendorCard({ vendor }: VendorCardProps) {
  const status = VENDOR_STATUS_META[vendor.status];

  return (
    <Link
      to={`/vendors/${encodeURIComponent(vendor.name)}`}
      className="group block h-full rounded-2xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
      aria-label={`${vendor.name}: ${status.label}, ${vendor.total_decisions} decisions`}
    >
      <BentoCard className="h-full" padding="md">
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 items-center gap-3">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-violet-600 text-sm font-bold text-white shadow-md">
              {initials(vendor.name)}
            </span>
            <div className="min-w-0">
              <h2 className="truncate font-semibold text-slate-900">{vendor.name}</h2>
              <p className="truncate text-xs text-slate-500">Payment terms: {vendor.payment_terms}</p>
            </div>
          </div>
          <span className={cx('shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset', status.badge)} title={status.description}>
            {status.label}
          </span>
        </div>

        <div className="mt-5 grid grid-cols-2 gap-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Decisions</p>
            <p className="tabular mt-1 text-2xl font-bold text-slate-900">{formatNumber(vendor.total_decisions)}</p>
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Approval rate</p>
            <p className="tabular mt-1 text-2xl font-bold text-slate-900">{vendor.total_decisions ? formatPercent(vendor.approval_rate) : '—'}</p>
            <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-slate-100">
              <div
                className="bar-grow h-full rounded-full bg-gradient-to-r from-emerald-500 to-teal-500"
                style={{ width: formatPercent(vendor.approval_rate) }}
              />
            </div>
          </div>
        </div>

        <div className="mt-5">
          <PriceHistory prices={vendor.historical_prices} />
        </div>

        {vendor.recent_exceptions.length > 0 && (
          <div className="mt-5">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Recent exceptions</p>
            <ul className="mt-2 space-y-1.5">
              {vendor.recent_exceptions.slice(0, 3).map((exception) => (
                <li key={`${exception.invoice_id}-${exception.type}`} className="flex items-center gap-2 text-xs text-slate-600">
                  <span className={cx('h-1.5 w-1.5 shrink-0 rounded-full', SEVERITY_META[exception.severity].dot)} aria-hidden="true" />
                  <span className="truncate">
                    {humanize(exception.type)} · {formatVariance(exception.variance_percent)}
                  </span>
                  <span className="ml-auto font-mono text-slate-400">{exception.invoice_id}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <p className="mt-auto flex items-center gap-1 pt-5 text-sm font-semibold text-blue-600">
          View memory
          <ArrowRight className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-0.5" aria-hidden="true" />
        </p>
      </BentoCard>
    </Link>
  );
}
