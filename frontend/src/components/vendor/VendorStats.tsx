import type { ReactNode } from 'react';
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { LineChart as LineChartIcon } from 'lucide-react';
import BentoCard from '../common/BentoCard';
import EmptyState from '../common/EmptyState';
import { VENDOR_STATUS_META } from '../../utils/constants';
import { cx, formatCurrency, formatNumber, formatPercent } from '../../utils/formatters';
import type { VendorProfile } from '../../types';

interface VendorStatsProps {
  vendor: VendorProfile;
}

function Tile({ label, children, hint }: { label: string; children: ReactNode; hint?: ReactNode }) {
  return (
    <BentoCard padding="md" hoverable={false}>
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <div className="mt-2">{children}</div>
      {hint && <p className="mt-2 text-xs text-slate-500">{hint}</p>}
    </BentoCard>
  );
}

export default function VendorStats({ vendor }: VendorStatsProps) {
  const status = VENDOR_STATUS_META[vendor.status];
  const prices = vendor.historical_prices;
  const low = prices.length ? Math.min(...prices) : null;
  const high = prices.length ? Math.max(...prices) : null;
  const series = prices.map((price, index) => ({ label: `#${index + 1}`, price }));

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Tile label="Human decisions" hint="Approvals, rejections and holds">
          <p className="tabular text-3xl font-bold text-slate-900">{formatNumber(vendor.total_decisions)}</p>
        </Tile>
        <Tile label="Approval rate">
          <p className="tabular text-3xl font-bold text-slate-900">{vendor.total_decisions ? formatPercent(vendor.approval_rate) : '—'}</p>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100">
            <div className="bar-grow h-full rounded-full bg-gradient-to-r from-emerald-500 to-teal-500" style={{ width: formatPercent(vendor.approval_rate) }} />
          </div>
        </Tile>
        <Tile label="Status" hint={status.description}>
          <span className={cx('inline-flex rounded-full px-3 py-1 text-sm font-semibold ring-1 ring-inset', status.badge)}>{status.label}</span>
        </Tile>
        <Tile label="Price range" hint={`${prices.length} historical price${prices.length === 1 ? '' : 's'} on file`}>
          <p className="tabular text-xl font-bold text-slate-900">
            {low === null || high === null ? '—' : low === high ? formatCurrency(low) : `${formatCurrency(low)} – ${formatCurrency(high)}`}
          </p>
        </Tile>
      </div>

      <BentoCard
        hoverable={false}
        icon={<LineChartIcon className="h-5 w-5" aria-hidden="true" />}
        title="Historical unit prices"
        subtitle="From the vendor profile: context for the agent, never an approval"
      >
        {series.length > 1 ? (
          <div className="h-56" role="img" aria-label={`Historical prices: ${prices.map((p) => formatCurrency(p)).join(', ')}`}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={series} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="vendor-price-fill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 12, fill: '#64748b' }} axisLine={false} tickLine={false} />
                <YAxis
                  tick={{ fontSize: 12, fill: '#64748b' }}
                  axisLine={false}
                  tickLine={false}
                  width={72}
                  domain={['auto', 'auto']}
                  tickFormatter={(value: number) => formatCurrency(value)}
                />
                <Tooltip
                  contentStyle={{ backgroundColor: '#fff', border: '1px solid #e2e8f0', borderRadius: 12, fontSize: 13 }}
                  formatter={(value) => [formatCurrency(Number(value)), 'Unit price']}
                />
                <Area type="monotone" dataKey="price" stroke="#7c3aed" strokeWidth={2} fill="url(#vendor-price-fill)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <EmptyState
            compact
            icon={LineChartIcon}
            title={series.length === 1 ? `One price on file: ${formatCurrency(prices[0] ?? 0)}` : 'No price history on file'}
            description="A trend appears once the vendor profile lists two or more prices."
          />
        )}
      </BentoCard>
    </div>
  );
}
