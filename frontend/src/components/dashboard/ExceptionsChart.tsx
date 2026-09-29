import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { ChartColumn } from 'lucide-react';
import EmptyState from '../common/EmptyState';
import { humanize } from '../../utils/formatters';

interface ExceptionsChartProps {
  data: { type: string; count: number }[];
}

// One gradient per exception type; ids are referenced by the bars below.
const GRADIENTS = [
  { id: 'exceptions-blue', from: '#3b82f6', to: '#8b5cf6' },
  { id: 'exceptions-orange', from: '#f97316', to: '#ec4899' },
  { id: 'exceptions-teal', from: '#10b981', to: '#06b6d4' },
];

export default function ExceptionsChart({ data }: ExceptionsChartProps) {
  const total = data.reduce((sum, row) => sum + row.count, 0);
  if (total === 0) {
    return (
      <EmptyState
        compact
        icon={ChartColumn}
        title="No exceptions yet"
        description="Price and quantity mismatches appear here as invoices are processed."
      />
    );
  }

  const rows = data.map((row) => ({ ...row, label: humanize(row.type) }));

  return (
    <div>
      <div className="h-64" role="img" aria-label={`Exceptions by type: ${rows.map((r) => `${r.label} ${r.count}`).join(', ')}`}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
            <defs>
              {GRADIENTS.map((g) => (
                <linearGradient key={g.id} id={g.id} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={g.from} />
                  <stop offset="100%" stopColor={g.to} />
                </linearGradient>
              ))}
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
            <XAxis dataKey="label" tick={{ fontSize: 12, fill: '#64748b' }} axisLine={false} tickLine={false} />
            <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: '#64748b' }} axisLine={false} tickLine={false} />
            <Tooltip
              cursor={{ fill: 'rgba(148, 163, 184, 0.12)' }}
              contentStyle={{ backgroundColor: '#fff', border: '1px solid #e2e8f0', borderRadius: 12, fontSize: 13 }}
              formatter={(value) => [value, 'Exceptions']}
            />
            <Bar dataKey="count" radius={[8, 8, 0, 0]} maxBarSize={72}>
              {rows.map((row, index) => (
                <Cell key={row.type} fill={`url(#${GRADIENTS[index % GRADIENTS.length]!.id})`} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-3 text-sm text-slate-500">
        <span className="tabular font-semibold text-slate-900">{total}</span> exception{total === 1 ? '' : 's'} found by the rule
        engine across every processed invoice.
      </p>
    </div>
  );
}
