import { ArrowRight, ChartColumn, CircleAlert, CircleCheck, FileText, Repeat, Users, Workflow } from 'lucide-react';
import BentoCard from '../common/BentoCard';
import GradientButton from '../common/GradientButton';
import Mascot from '../common/Mascot';
import ExceptionsChart from './ExceptionsChart';
import QuickActions from './QuickActions';
import RecentMemoriesCard from './RecentMemoriesCard';
import StatCard from './StatCard';
import { APP_TAGLINE, LEARNING_LOOP_STEPS } from '../../utils/constants';
import { cx, formatNumber, formatPercent } from '../../utils/formatters';
import { MASCOT_STATES } from '../../utils/mascot';
import type { DashboardData, DashboardStats } from '../../types';

/** The mascot reports what it has learned so far, from real counts. */
function MascotHero({ stats, className }: { stats: DashboardStats; className?: string }) {
  const learned = stats.memories_retained;
  const state = MASCOT_STATES[learned === 0 ? 'firstDay' : 'smarter'];
  const plural = (n: number, word: string) => `${formatNumber(n)} ${word}${n === 1 ? '' : 's'}`;
  const detail =
    learned === 0
      ? 'Review an exception and give a reason: that decision becomes my first memory.'
      : `${plural(learned, 'decision')} remembered in Hindsight · ${plural(stats.active_vendors, 'vendor')} seen`;

  return (
    <section
      className={cx(
        'relative overflow-hidden rounded-2xl bg-gradient-to-br from-[#0b1024] via-[#131a3f] to-[#221654] p-6 text-white shadow-lift sm:p-8',
        className,
      )}
    >
      <div className="pointer-events-none absolute -left-20 -top-20 h-64 w-64 rounded-full bg-teal-400/20 blur-3xl" aria-hidden="true" />
      <div className="pointer-events-none absolute -bottom-24 right-8 h-72 w-72 rounded-full bg-violet-500/25 blur-3xl" aria-hidden="true" />
      <div className="relative flex flex-col gap-6 sm:flex-row sm:items-center">
        <Mascot pose={state.pose} tone={state.tone} size="xl" label={`PaySage mascot: ${state.title}`} />
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-300">{state.title}</p>
          <h2 className="mt-2 text-2xl font-bold tracking-tight sm:text-3xl">{APP_TAGLINE}</h2>
          <p className="mt-3 text-base text-slate-100">“{state.line}”</p>
          <p className="mt-1.5 text-sm text-slate-400">{detail}</p>
        </div>
        <GradientButton to="/review" size="lg" icon={<ArrowRight className="h-5 w-5" aria-hidden="true" />} className="self-start sm:self-center">
          {stats.pending_decisions > 0 ? `Review ${formatNumber(stats.pending_decisions)} waiting` : 'Review invoices'}
        </GradientButton>
      </div>
    </section>
  );
}

interface DashboardGridProps {
  data: DashboardData;
  stats: DashboardStats;
}

/** Processed → decided by a human → remembered. Each bar is relative to invoices processed. */
function LearningLoopCard({ stats, className }: { stats: DashboardStats; className?: string }) {
  const base = Math.max(stats.total_processed, 1);
  const rows = [
    { label: 'Invoices processed', value: stats.total_processed, bar: 'from-blue-500 to-indigo-500' },
    { label: 'Decided by a reviewer', value: stats.total_decisions, bar: 'from-violet-500 to-fuchsia-500' },
    { label: 'Remembered in Hindsight', value: stats.memories_retained, bar: 'from-emerald-500 to-teal-500' },
  ];

  return (
    <BentoCard
      className={className}
      hoverable={false}
      icon={<Repeat className="h-5 w-5" aria-hidden="true" />}
      title="Learning loop"
      subtitle="How much review work has turned into memory"
    >
      <ul className="space-y-4">
        {rows.map((row) => (
          <li key={row.label}>
            <div className="flex items-baseline justify-between text-sm">
              <span className="font-medium text-slate-700">{row.label}</span>
              <span className="tabular font-semibold text-slate-900">{formatNumber(row.value)}</span>
            </div>
            <div className="mt-1.5 h-2.5 overflow-hidden rounded-full bg-slate-100">
              <div
                className={cx('bar-grow h-full rounded-full bg-gradient-to-r', row.bar)}
                style={{ width: `${Math.min(100, (row.value / base) * 100)}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
      <div className="mt-5 grid grid-cols-2 gap-3 border-t border-slate-100 pt-4 text-sm">
        <div>
          <p className="text-xs text-slate-500">Awaiting a decision</p>
          <p className="tabular text-lg font-semibold text-amber-600">{formatNumber(stats.pending_decisions)}</p>
        </div>
        <div>
          <p className="text-xs text-slate-500">Decisions retained</p>
          <p className="tabular text-lg font-semibold text-emerald-600">
            {stats.total_decisions ? formatPercent(stats.memories_retained / stats.total_decisions) : '—'}
          </p>
        </div>
      </div>
    </BentoCard>
  );
}

function HowItLearns({ className }: { className?: string }) {
  return (
    <BentoCard
      className={className}
      hoverable={false}
      gradient
      gradientFrom="from-slate-900"
      gradientTo="to-slate-800"
    >
      <div className="flex items-center gap-2 text-white">
        <Workflow className="h-5 w-5 text-violet-300" aria-hidden="true" />
        <h2 className="text-base font-semibold">How every recommendation is made</h2>
      </div>
      <ol className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
        {LEARNING_LOOP_STEPS.map((step, index) => (
          <li key={step.title} className="relative rounded-xl bg-white/5 p-3 ring-1 ring-inset ring-white/10">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-violet-300">{String(index + 1).padStart(2, '0')}</span>
              <Mascot pose={step.pose} tone="violet" size="sm" animate={false} />
            </div>
            <p className="mt-2 text-sm font-semibold text-white">{step.title}</p>
            <p className="mt-1 text-xs leading-relaxed text-slate-400">{step.text}</p>
            {index < LEARNING_LOOP_STEPS.length - 1 && (
              <ArrowRight className="absolute -right-2.5 top-1/2 hidden h-4 w-4 -translate-y-1/2 text-slate-500 lg:block" aria-hidden="true" />
            )}
          </li>
        ))}
      </ol>
    </BentoCard>
  );
}

export default function DashboardGrid({ data, stats }: DashboardGridProps) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <MascotHero stats={stats} className="sm:col-span-2 lg:col-span-4" />
      <StatCard
        label="Invoices processed"
        value={formatNumber(data.total_processed)}
        hint="Checked against their purchase orders"
        icon={FileText}
        tone="blue"
      />
      <StatCard
        label="Exceptions detected"
        value={formatNumber(data.total_exceptions)}
        hint={`${formatNumber(stats.pending_decisions)} invoice${stats.pending_decisions === 1 ? '' : 's'} awaiting a decision`}
        icon={CircleAlert}
        tone="orange"
      />
      <StatCard
        label="Approval rate"
        value={stats.total_decisions ? formatPercent(data.approval_rate) : '—'}
        hint={`Of ${formatNumber(stats.total_decisions)} human decision${stats.total_decisions === 1 ? '' : 's'}`}
        icon={CircleCheck}
        tone="green"
      />
      <StatCard
        label="Active vendors"
        value={formatNumber(data.active_vendors)}
        hint="With at least one processed invoice"
        icon={Users}
        tone="purple"
      />

      <BentoCard
        className="sm:col-span-2"
        hoverable={false}
        icon={<ChartColumn className="h-5 w-5" aria-hidden="true" />}
        title="Exceptions by type"
        subtitle="What the rule engine flagged"
      >
        <ExceptionsChart data={data.exception_breakdown} />
      </BentoCard>
      <LearningLoopCard stats={stats} className="sm:col-span-2" />

      <RecentMemoriesCard memories={data.recent_memories} className="sm:col-span-2 lg:col-span-3" />
      <QuickActions pending={stats.pending_decisions} className="sm:col-span-2 lg:col-span-1" />

      <HowItLearns className="sm:col-span-2 lg:col-span-4" />
    </div>
  );
}
